"""Orchestrates ESI market data fetching and persistence."""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.esi import EsiClient
from app.models.market import MarketHistoryDaily, MarketOrderSnapshot, MarketPrice

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Fetches market data from ESI and persists to the database."""

    def __init__(self, esi: EsiClient, db: AsyncSession):
        self.esi = esi
        self.db = db

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    async def fetch_orders_for_region(
        self,
        region_id: int,
        order_type: str = "all",
    ) -> int:
        """Fetch all market orders for a region and persist them.

        Returns the number of orders stored.
        """
        fetched_at = datetime.datetime.now(datetime.timezone.utc)
        orders = await self.esi.get_market_orders(region_id, order_type=order_type)

        count = 0
        for batch in _chunk(orders, 1000):
            rows: list[dict] = []
            for o in batch:
                rows.append(
                    dict(
                        order_id=o["order_id"],
                        type_id=o["type_id"],
                        region_id=region_id,
                        location_id=o["location_id"],
                        system_id=o.get("system_id"),
                        is_buy_order=o["is_buy_order"],
                        price=o["price"],
                        volume_remain=o["volume_remain"],
                        volume_total=o["volume_total"],
                        min_volume=o.get("min_volume", 1),
                        duration=o["duration"],
                        range=o["range"],
                        issued=_parse_esi_datetime(o["issued"]),
                        fetched_at=fetched_at,
                    )
                )

            # Use INSERT … ON CONFLICT DO NOTHING
            stmt = _build_insert_on_conflict_do_nothing(
                MarketOrderSnapshot,
                rows,
            )
            await self.db.execute(stmt)
            count += len(rows)

        await self.db.commit()

        # Update the fetch cache so dashboard queries use the latest timestamp
        await self.db.execute(text("""
            INSERT INTO latest_fetch_cache (region_id, fetched_at)
            VALUES (:region_id, :fetched_at)
            ON CONFLICT (region_id) DO UPDATE SET fetched_at = EXCLUDED.fetched_at
        """), {"region_id": region_id, "fetched_at": fetched_at})

        # Refresh the summary caches (so dashboard reads are instant)
        await self.db.execute(text("""
            INSERT INTO order_stats_cache (id, total_orders, buy_orders, sell_orders, total_isk)
            SELECT 1, COUNT(*), COUNT(*) FILTER (WHERE is_buy_order),
                   COUNT(*) FILTER (WHERE NOT is_buy_order),
                   COALESCE(SUM(price * volume_remain), 0)
            FROM market_order_snapshot mos
            JOIN latest_fetch_cache lc
                ON mos.fetched_at = lc.fetched_at AND mos.region_id = lc.region_id
            ON CONFLICT (id) DO UPDATE SET
                total_orders=EXCLUDED.total_orders, buy_orders=EXCLUDED.buy_orders,
                sell_orders=EXCLUDED.sell_orders, total_isk=EXCLUDED.total_isk, updated_at=now()
        """))
        await self.db.execute(text("""
            INSERT INTO region_summary_cache (region_id, order_count, buy_count, sell_count, total_isk)
            SELECT mos.region_id, COUNT(*),
                   COUNT(*) FILTER (WHERE is_buy_order),
                   COUNT(*) FILTER (WHERE NOT is_buy_order),
                   COALESCE(SUM(price * volume_remain), 0)
            FROM market_order_snapshot mos
            JOIN latest_fetch_cache lc
                ON mos.fetched_at = lc.fetched_at AND mos.region_id = lc.region_id
            GROUP BY mos.region_id
            ON CONFLICT (region_id) DO UPDATE SET
                order_count=EXCLUDED.order_count, buy_count=EXCLUDED.buy_count,
                sell_count=EXCLUDED.sell_count, total_isk=EXCLUDED.total_isk, updated_at=now()
        """))

        # Refresh hot items cache
        await self.db.execute(text("DELETE FROM hot_item_cache"))
        await self.db.execute(text("""
            INSERT INTO hot_item_cache (type_id, region_id, current_vol, prev_vol, volume_change_pct, abs_change)
            WITH prev_per_region AS (
                SELECT mos2.region_id, MAX(mos2.fetched_at) AS ts
                FROM market_order_snapshot mos2
                JOIN latest_fetch_cache lc2 ON lc2.region_id = mos2.region_id
                WHERE mos2.fetched_at < lc2.fetched_at - INTERVAL '12 hours'
                GROUP BY mos2.region_id
            ),
            current_vol AS (
                SELECT mos.type_id, mos.region_id, SUM(mos.volume_remain) AS vol
                FROM market_order_snapshot mos
                JOIN latest_fetch_cache lc ON mos.fetched_at = lc.fetched_at AND mos.region_id = lc.region_id
                GROUP BY mos.type_id, mos.region_id
            ),
            prev_vol AS (
                SELECT mos.type_id, mos.region_id, SUM(mos.volume_remain) AS vol
                FROM market_order_snapshot mos
                JOIN prev_per_region pp ON mos.fetched_at = pp.ts AND mos.region_id = pp.region_id
                GROUP BY mos.type_id, mos.region_id
            )
            SELECT cv.type_id, cv.region_id,
                   COALESCE(cv.vol,0)::bigint, COALESCE(pv.vol,0)::bigint,
                   CASE WHEN COALESCE(pv.vol,0) > 0 THEN ((cv.vol - pv.vol)/pv.vol)*100 ELSE 0 END,
                   ABS(COALESCE(cv.vol,0) - COALESCE(pv.vol,0))::bigint
            FROM current_vol cv
            LEFT JOIN prev_vol pv ON cv.type_id = pv.type_id AND cv.region_id = pv.region_id
            WHERE COALESCE(cv.vol,0) > 0
            ORDER BY ABS(COALESCE(cv.vol,0) - COALESCE(pv.vol,0)) DESC
            LIMIT 100
        """))

        await self.db.commit()

        logger.info(
            "Fetched %d orders for region %d (order_type=%s)",
            count,
            region_id,
            order_type,
        )
        return count

    async def fetch_orders_all_regions(
        self,
        region_ids: list[int],
        order_type: str = "all",
    ) -> dict[int, int]:
        """Fetch orders for all specified regions. Returns {region_id: count}."""
        results: dict[int, int] = {}
        for region_id in region_ids:
            try:
                count = await self.fetch_orders_for_region(region_id, order_type)
                results[region_id] = count
            except Exception:
                logger.exception("Failed to fetch orders for region %d", region_id)
                results[region_id] = 0
        return results

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def fetch_history_for_item(
        self,
        region_id: int,
        type_id: int,
    ) -> int:
        """Fetch daily market history for one item in one region.

        Uses INSERT … ON CONFLICT DO NOTHING to avoid duplicates.
        Returns the number of new rows inserted.
        """
        rows = await self.esi.get_market_history(region_id, type_id)
        fetched_at = datetime.datetime.now(datetime.timezone.utc)
        inserted = 0

        for batch in _chunk(rows, 500):
            batch_rows: list[dict] = []
            for r in batch:
                batch_rows.append(
                    dict(
                        type_id=type_id,
                        region_id=region_id,
                        date=datetime.date.fromisoformat(r["date"]),
                        average=r["average"],
                        highest=r["highest"],
                        lowest=r["lowest"],
                        order_count=r["order_count"],
                        volume=r["volume"],
                        fetched_at=fetched_at,
                    )
                )
            stmt = _build_insert_on_conflict_do_nothing(
                MarketHistoryDaily,
                batch_rows,
                constraint="uq_history_type_region_date",
            )
            await self.db.execute(stmt)
            inserted += len(batch_rows)

        await self.db.commit()
        return inserted

    async def fetch_history_for_hub_items(
        self,
        region_id: int,
        type_ids: list[int],
    ) -> int:
        """Fetch history for a batch of items.

        A maximum of 300 items will be processed per call to avoid
        hitting the market-history rate limit.
        """
        total = 0
        for type_id in type_ids[:300]:
            try:
                inserted = await self.fetch_history_for_item(region_id, type_id)
                total += inserted
            except Exception:
                logger.exception(
                    "Failed to fetch history for type_id=%d region=%d",
                    type_id,
                    region_id,
                )
        return total

    # ------------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------------

    async def fetch_prices_all(self) -> int:
        """Fetch universe-wide average prices and persist."""
        rows = await self.esi.get_market_prices()
        fetched_at = datetime.datetime.now(datetime.timezone.utc)
        inserted = 0

        for batch in _chunk(rows, 1000):
            batch_rows: list[dict] = []
            for r in batch:
                batch_rows.append(
                    dict(
                        type_id=r["type_id"],
                        adjusted_price=r.get("adjusted_price"),
                        average_price=r.get("average_price"),
                        fetched_at=fetched_at,
                    )
                )
            stmt = _build_upsert(
                MarketPrice,
                batch_rows,
                update_columns=["adjusted_price", "average_price", "fetched_at"],
            )
            await self.db.execute(stmt)
            inserted += len(batch_rows)

        await self.db.commit()
        logger.info("Fetched %d market price entries", inserted)
        return inserted

    # ------------------------------------------------------------------
    # Type IDs for a region
    # ------------------------------------------------------------------

    async def resolve_unknown_items(self, limit: int = 500) -> int:
        """Resolve item names for unknown type_ids in the latest snapshot.

        Queries ESI for each unknown type_id and inserts into the item table.
        Returns the number of items resolved.
        """
        from sqlalchemy import text
        from app.services.sde_loader import SdeLoader

        # Find all distinct type_ids in the latest snapshot that aren't in item table
        result = await self.db.execute(text("""
            SELECT DISTINCT mos.type_id
            FROM market_order_snapshot mos
            WHERE mos.fetched_at = (SELECT MAX(fetched_at) FROM market_order_snapshot)
              AND mos.type_id NOT IN (SELECT type_id FROM item)
            LIMIT :limit
        """), {"limit": limit})

        type_ids = {row[0] for row in result.fetchall()}
        if not type_ids:
            logger.info("All items already resolved")
            return 0

        logger.info("Resolving %d unknown item names via ESI (zh)...", len(type_ids))
        loader = SdeLoader(self.esi, self.db)
        names = await loader.resolve_items(type_ids)
        return len(names)

    async def get_active_type_ids(self, region_id: int) -> list[int]:
        """Get type_ids with active orders in a region."""
        return await self.esi.get_markets_region_types(region_id)

    # ------------------------------------------------------------------
    # Latest snapshot helper
    # ------------------------------------------------------------------

    async def get_latest_fetch_time(self) -> datetime.datetime | None:
        """Get the most recent fetched_at timestamp from order snapshots."""
        result = await self.db.execute(
            text(
                "SELECT MAX(fetched_at) FROM market_order_snapshot"
            )
        )
        row = result.fetchone()
        return row[0] if row and row[0] else None


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _chunk(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _parse_esi_datetime(s: str) -> datetime.datetime:
    """Parse an ESI ISO-8601 datetime string into a UTC-aware datetime."""
    dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _build_insert_on_conflict_do_nothing(
    model,
    rows: list[dict],
    constraint: str = "uq_order_fetch",
):
    """Build an INSERT … ON CONFLICT DO NOTHING statement for the given model."""
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(model).values(rows)
    return stmt.on_conflict_do_nothing(constraint=constraint)


def _build_upsert(
    model,
    rows: list[dict],
    update_columns: list[str],
    constraint: str = "market_price_type_id_key",
):
    """Build an INSERT … ON CONFLICT … DO UPDATE statement."""
    from sqlalchemy.dialects.postgresql import insert

    stmt = insert(model).values(rows)
    set_ = {c: getattr(stmt.excluded, c) for c in update_columns}
    return stmt.on_conflict_do_update(constraint=constraint, set_=set_)
