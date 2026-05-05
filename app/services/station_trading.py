"""Station trading service: same-station buy-low-sell-high discovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class StationTradingOpportunity:
    type_id: int
    item_name: str
    region_id: int
    station_id: int
    buy_price: float
    sell_price: float
    spread: float
    margin: float
    buy_volume: int
    sell_volume: int
    potential_quantity: int
    potential_profit: float


class StationTradingService:
    """Discovers and tracks same-station trading opportunities."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_opportunities(
        self,
        region_id: int,
        station_id: int | None = None,
        min_margin: float = 0.10,
        max_investment: float | None = None,
        sort_by: str = "potential_profit",
        limit: int = 100,
    ) -> list[StationTradingOpportunity]:
        """Find items with a profitable buy/sell spread in the same station.

        Looks at the latest snapshot for orders where the best buy order
        (highest buy) is at the same station as the best sell order
        (lowest sell), and the buy price is lower than the sell price.
        """
        sql = text("""
        WITH station_spreads AS (
            SELECT
                mos.type_id,
                mos.region_id,
                mos.location_id AS station_id,
                MAX(CASE WHEN mos.is_buy_order = TRUE THEN mos.price END)
                    FILTER (WHERE mos.is_buy_order = TRUE
                            AND mos.volume_remain >= 1)
                    AS max_buy_price,
                COALESCE(SUM(CASE WHEN mos.is_buy_order = TRUE
                    THEN mos.volume_remain END), 0) AS buy_volume,
                MIN(CASE WHEN mos.is_buy_order = FALSE THEN mos.price END)
                    FILTER (WHERE mos.is_buy_order = FALSE
                            AND mos.volume_remain >= 1)
                    AS min_sell_price,
                COALESCE(SUM(CASE WHEN mos.is_buy_order = FALSE
                    THEN mos.volume_remain END), 0) AS sell_volume
            FROM market_order_snapshot mos
            JOIN latest_fetch_cache lc
                ON mos.fetched_at = lc.fetched_at AND mos.region_id = lc.region_id
            WHERE mos.region_id = :region_id
              AND (:station_id IS NULL OR mos.location_id = :station_id)
            GROUP BY mos.type_id, mos.region_id, mos.location_id
        )
        SELECT
            type_id, region_id, station_id,
            max_buy_price AS buy_price,
            min_sell_price AS sell_price,
            (min_sell_price - max_buy_price) AS spread,
            ((min_sell_price - max_buy_price)
             / NULLIF(max_buy_price, 0)) AS margin,
            buy_volume::int,
            sell_volume::int,
            LEAST(buy_volume, sell_volume)::int AS potential_quantity,
            ((min_sell_price - max_buy_price)
             * LEAST(buy_volume, sell_volume)) AS potential_profit
        FROM station_spreads
        WHERE max_buy_price > 0
          AND min_sell_price > max_buy_price
          AND ((min_sell_price - max_buy_price)
               / NULLIF(max_buy_price, 0)) >= :min_margin
          AND (:max_investment IS NULL
               OR max_buy_price <= CAST(:max_investment AS float))
        ORDER BY {} DESC
        LIMIT :limit
        """.format("margin" if sort_by == "margin" else "potential_profit"))

        result = await self.db.execute(
            sql,
            {
                "region_id": region_id,
                "station_id": station_id,
                "min_margin": min_margin,
                "max_investment": max_investment,
                "limit": limit,
            },
        )
        rows = result.fetchall()

        # Resolve item names
        from app.models.item import Item
        from sqlalchemy import select

        type_ids = {r.type_id for r in rows}
        names: dict[int, str] = {}
        if type_ids:
            item_result = await self.db.execute(
                select(Item.type_id, Item.name).where(Item.type_id.in_(type_ids))
            )
            names = {r.type_id: r.name for r in item_result.fetchall()}

        return [
            StationTradingOpportunity(
                type_id=r.type_id,
                item_name=names.get(r.type_id, f"#{r.type_id}"),
                region_id=r.region_id,
                station_id=r.station_id,
                buy_price=r.buy_price,
                sell_price=r.sell_price,
                spread=r.spread,
                margin=r.margin,
                buy_volume=r.buy_volume,
                sell_volume=r.sell_volume,
                potential_quantity=r.potential_quantity,
                potential_profit=r.potential_profit,
            )
            for r in rows
        ]

    async def get_opportunity_detail(
        self, type_id: int, region_id: int
    ) -> dict | None:
        """Get detailed buy/sell spread for a specific item in a region."""
        opps = await self.find_opportunities(
            region_id=region_id,
            min_margin=0.0,
            limit=500,
        )
        for o in opps:
            if o.type_id == type_id:
                return {
                    "type_id": o.type_id,
                    "item_name": o.item_name,
                    "region_id": o.region_id,
                    "station_id": o.station_id,
                    "buy_price": o.buy_price,
                    "sell_price": o.sell_price,
                    "spread": o.spread,
                    "margin": o.margin,
                    "buy_volume": o.buy_volume,
                    "sell_volume": o.sell_volume,
                    "potential_quantity": o.potential_quantity,
                    "potential_profit": o.potential_profit,
                }
        return None
