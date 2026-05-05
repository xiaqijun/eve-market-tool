"""Cross-region arbitrage detection engine.

Compares prices across trade hub regions to find items that can be
bought low in one region and sold high in another.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ArbitrageResult:
    type_id: int
    item_name: str
    buy_region_id: int
    buy_region_name: str
    sell_region_id: int
    sell_region_name: str
    buy_price: float
    sell_price: float
    buy_volume: int
    sell_volume: int
    quantity: int
    profit_per_unit: float
    profit_margin: float
    total_profit: float


class ArbitrageEngine:
    """Detects cross-region arbitrage opportunities from order snapshots.

    Uses the LATEST snapshot for each region to compute per-item
    best buy/sell prices, then cross-references regions.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def scan(
        self,
        min_profit_margin: float = 0.05,
        min_profit_isk: float = 1_000_000,
        top_n: int = 100,
    ) -> list[ArbitrageResult]:
        """Scan for arbitrage opportunities and persist them.

        Returns the top results sorted by total_profit descending.
        """
        detected_at = datetime.datetime.now(datetime.timezone.utc)

        # The CTE gets the latest order snapshot per region, then
        # computes per-item buy/sell aggregations.  The outer join
        # pairs buy_region (where we buy cheap from a sell order)
        # with sell_region (where we sell to a high buy order).
        sql = text("""
        WITH region_prices AS (
            SELECT
                mos.type_id,
                mos.region_id,
                MIN(CASE WHEN mos.is_buy_order = FALSE THEN mos.price END)
                    FILTER (WHERE mos.is_buy_order = FALSE
                            AND mos.volume_remain >= 1)
                    AS min_sell_price,
                MAX(CASE WHEN mos.is_buy_order = TRUE THEN mos.price END)
                    FILTER (WHERE mos.is_buy_order = TRUE
                            AND mos.volume_remain >= 1)
                    AS max_buy_price,
                COALESCE(SUM(CASE WHEN mos.is_buy_order = FALSE
                    THEN mos.volume_remain END), 0) AS total_sell_volume,
                COALESCE(SUM(CASE WHEN mos.is_buy_order = TRUE
                    THEN mos.volume_remain END), 0) AS total_buy_volume
            FROM market_order_snapshot mos
            JOIN latest_fetch_cache lc
                ON mos.fetched_at = lc.fetched_at AND mos.region_id = lc.region_id
            WHERE mos.region_id = ANY(:region_ids)
            GROUP BY mos.type_id, mos.region_id
        )
        SELECT
            buy_rp.type_id,
            buy_rp.region_id AS buy_region_id,
            sell_rp.region_id AS sell_region_id,
            buy_rp.min_sell_price AS buy_price,
            sell_rp.max_buy_price AS sell_price,
            buy_rp.total_sell_volume AS buy_volume,
            sell_rp.total_buy_volume AS sell_volume,
            LEAST(buy_rp.total_sell_volume, sell_rp.total_buy_volume)
                AS quantity,
            (sell_rp.max_buy_price - buy_rp.min_sell_price) AS profit_per_unit,
            ((sell_rp.max_buy_price - buy_rp.min_sell_price)
             / NULLIF(buy_rp.min_sell_price, 0)) AS profit_margin,
            ((sell_rp.max_buy_price - buy_rp.min_sell_price)
             * LEAST(buy_rp.total_sell_volume, sell_rp.total_buy_volume))
                AS total_profit
        FROM region_prices buy_rp
        JOIN region_prices sell_rp
            ON buy_rp.type_id = sell_rp.type_id
            AND buy_rp.region_id <> sell_rp.region_id
        WHERE buy_rp.min_sell_price > 0
          AND sell_rp.max_buy_price > 0
          AND buy_rp.min_sell_price < sell_rp.max_buy_price
        ORDER BY total_profit DESC
        LIMIT :top_n
        """)

        result = await self.db.execute(
            sql,
            {
                "region_ids": [10000002, 10000043, 10000032, 10000030, 10000042],
                "top_n": top_n,
            },
        )
        rows = result.fetchall()

        # Resolve names
        type_ids = {r.type_id for r in rows}
        region_ids = {r.buy_region_id for r in rows} | {r.sell_region_id for r in rows}
        names = await self._resolve_names(type_ids, region_ids)

        opportunities: list[ArbitrageResult] = []
        for r in rows:
            opp = ArbitrageResult(
                type_id=r.type_id,
                item_name=names["items"].get(r.type_id, f"Unknown #{r.type_id}"),
                buy_region_id=r.buy_region_id,
                buy_region_name=names["regions"].get(r.buy_region_id, f"#{r.buy_region_id}"),
                sell_region_id=r.sell_region_id,
                sell_region_name=names["regions"].get(r.sell_region_id, f"#{r.sell_region_id}"),
                buy_price=r.buy_price,
                sell_price=r.sell_price,
                buy_volume=r.buy_volume,
                sell_volume=r.sell_volume,
                quantity=r.quantity,
                profit_per_unit=r.profit_per_unit,
                profit_margin=r.profit_margin,
                total_profit=r.total_profit,
            )
            opportunities.append(opp)

        # Persist
        await self._persist(opportunities, detected_at)

        return opportunities

    async def get_price_comparison(
        self,
        type_id: int,
    ) -> list[dict]:
        """Get buy/sell prices for *type_id* across all tracked regions."""
        sql = text("""
        SELECT
            mos.region_id,
            r.name AS region_name,
            MIN(CASE WHEN mos.is_buy_order = FALSE THEN mos.price END)
                FILTER (WHERE mos.is_buy_order = FALSE
                        AND mos.volume_remain >= 1)
                AS min_sell_price,
            MAX(CASE WHEN mos.is_buy_order = TRUE THEN mos.price END)
                FILTER (WHERE mos.is_buy_order = TRUE
                        AND mos.volume_remain >= 1)
                AS max_buy_price,
            COALESCE(SUM(CASE WHEN mos.is_buy_order = FALSE
                THEN mos.volume_remain END), 0) AS sell_volume,
            COALESCE(SUM(CASE WHEN mos.is_buy_order = TRUE
                THEN mos.volume_remain END), 0) AS buy_volume
        FROM market_order_snapshot mos
        JOIN latest_fetch_cache lc
            ON mos.fetched_at = lc.fetched_at AND mos.region_id = lc.region_id
        LEFT JOIN region r ON r.eve_region_id = mos.region_id
        WHERE mos.type_id = :type_id
        GROUP BY mos.region_id, r.name
        ORDER BY min_sell_price ASC
        """)
        result = await self.db.execute(sql, {"type_id": type_id})
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_opportunities(
        self,
        limit: int = 50,
        min_margin: float = 0.0,
        min_profit: float = 0.0,
        region_id: int | None = None,
        sort_by: str = "total_profit",
    ) -> list[dict]:
        """Query stored arbitrage opportunities."""
        from sqlalchemy import desc, select

        from app.models.trading import ArbitrageOpportunity

        stmt = select(ArbitrageOpportunity)
        if min_margin > 0:
            stmt = stmt.where(ArbitrageOpportunity.profit_margin >= min_margin)
        if min_profit > 0:
            stmt = stmt.where(ArbitrageOpportunity.total_profit >= min_profit)
        if region_id is not None:
            stmt = stmt.where(
                (ArbitrageOpportunity.buy_region_id == region_id)
                | (ArbitrageOpportunity.sell_region_id == region_id)
            )
        col = getattr(ArbitrageOpportunity, sort_by, ArbitrageOpportunity.total_profit)
        stmt = stmt.order_by(desc(col)).limit(limit)

        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        # Resolve names
        type_ids = {r.type_id for r in rows}
        region_ids = {r.buy_region_id for r in rows} | {r.sell_region_id for r in rows}
        names = await self._resolve_names(type_ids, region_ids)

        return [
            {
                "id": r.id,
                "type_id": r.type_id,
                "item_name": names["items"].get(r.type_id, f"#{r.type_id}"),
                "buy_region_id": r.buy_region_id,
                "buy_region_name": names["regions"].get(r.buy_region_id, f"#{r.buy_region_id}"),
                "sell_region_id": r.sell_region_id,
                "sell_region_name": names["regions"].get(r.sell_region_id, f"#{r.sell_region_id}"),
                "buy_price": r.buy_price,
                "sell_price": r.sell_price,
                "buy_volume": r.buy_volume,
                "sell_volume": r.sell_volume,
                "quantity": r.quantity,
                "profit_per_unit": r.profit_per_unit,
                "profit_margin": r.profit_margin,
                "total_profit": r.total_profit,
                "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _resolve_names(
        self, type_ids: set[int], region_ids: set[int]
    ) -> dict:
        from sqlalchemy import select
        from app.models.item import Item
        from app.models.region import Region

        items: dict[int, str] = {}
        if type_ids:
            result = await self.db.execute(
                select(Item.type_id, Item.name).where(Item.type_id.in_(type_ids))
            )
            items = {r.type_id: r.name for r in result.fetchall()}

        regions: dict[int, str] = {}
        if region_ids:
            result = await self.db.execute(
                select(Region.eve_region_id, Region.name).where(
                    Region.eve_region_id.in_(region_ids)
                )
            )
            regions = {r.eve_region_id: r.name for r in result.fetchall()}

        return {"items": items, "regions": regions}

    async def _persist(
        self,
        opportunities: list[ArbitrageResult],
        detected_at: datetime.datetime,
    ) -> None:
        from sqlalchemy.dialects.postgresql import insert

        from app.models.trading import ArbitrageOpportunity

        if not opportunities:
            return

        rows = [
            dict(
                type_id=o.type_id,
                buy_region_id=o.buy_region_id,
                sell_region_id=o.sell_region_id,
                buy_price=o.buy_price,
                sell_price=o.sell_price,
                buy_volume=o.buy_volume,
                sell_volume=o.sell_volume,
                quantity=o.quantity,
                profit_per_unit=o.profit_per_unit,
                profit_margin=o.profit_margin,
                total_profit=o.total_profit,
                detected_at=detected_at,
            )
            for o in opportunities
        ]

        stmt = insert(ArbitrageOpportunity).values(rows)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_arb_opportunity")
        await self.db.execute(stmt)
        await self.db.commit()
