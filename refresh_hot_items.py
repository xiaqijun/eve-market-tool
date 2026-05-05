"""Populate hot_item_cache with separate buy/sell order volumes."""
import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text


async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM hot_item_cache"))
        await db.execute(text("""
        INSERT INTO hot_item_cache (type_id, region_id,
            current_vol, prev_vol, buy_vol, sell_vol, prev_buy_vol, prev_sell_vol,
            volume_change_pct, abs_change)
        WITH prev_per_region AS (
            SELECT mos2.region_id, MAX(mos2.fetched_at) AS ts
            FROM market_order_snapshot mos2
            JOIN latest_fetch_cache lc2 ON lc2.region_id = mos2.region_id
            WHERE mos2.fetched_at < lc2.fetched_at - INTERVAL '12 hours'
            GROUP BY mos2.region_id
        ),
        current_stats AS (
            SELECT mos.type_id, mos.region_id,
                   SUM(mos.volume_remain) AS total_vol,
                   SUM(mos.volume_remain) FILTER (WHERE mos.is_buy_order) AS buy_vol,
                   SUM(mos.volume_remain) FILTER (WHERE NOT mos.is_buy_order) AS sell_vol
            FROM market_order_snapshot mos
            JOIN latest_fetch_cache lc ON mos.fetched_at = lc.fetched_at AND mos.region_id = lc.region_id
            GROUP BY mos.type_id, mos.region_id
        ),
        prev_stats AS (
            SELECT mos.type_id, mos.region_id,
                   SUM(mos.volume_remain) AS total_vol,
                   SUM(mos.volume_remain) FILTER (WHERE mos.is_buy_order) AS buy_vol,
                   SUM(mos.volume_remain) FILTER (WHERE NOT mos.is_buy_order) AS sell_vol
            FROM market_order_snapshot mos
            JOIN prev_per_region pp ON mos.fetched_at = pp.ts AND mos.region_id = pp.region_id
            GROUP BY mos.type_id, mos.region_id
        )
        SELECT cv.type_id, cv.region_id,
               COALESCE(cv.total_vol,0)::bigint, COALESCE(pv.total_vol,0)::bigint,
               COALESCE(cv.buy_vol,0)::bigint, COALESCE(cv.sell_vol,0)::bigint,
               COALESCE(pv.buy_vol,0)::bigint, COALESCE(pv.sell_vol,0)::bigint,
               CASE WHEN COALESCE(pv.total_vol,0) > 0
                    THEN ((cv.total_vol - pv.total_vol)/pv.total_vol)*100 ELSE 0 END,
               ABS(COALESCE(cv.total_vol,0) - COALESCE(pv.total_vol,0))::bigint
        FROM current_stats cv
        LEFT JOIN prev_stats pv ON cv.type_id = pv.type_id AND cv.region_id = pv.region_id
        WHERE COALESCE(cv.total_vol,0) > 0
        ORDER BY ABS(COALESCE(cv.total_vol,0) - COALESCE(pv.total_vol,0)) DESC
        LIMIT 100
        """))
        await db.commit()

        result = await db.execute(text("SELECT COUNT(*) FROM hot_item_cache"))
        print(f"Hot items refreshed: {result.fetchone()[0]} rows")


if __name__ == "__main__":
    asyncio.run(main())
