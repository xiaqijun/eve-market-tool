"""Dashboard aggregation service: overview, trends, hot items, region summaries."""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DashboardService:
    """Aggregates market data for the dashboard overview."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_overview(self) -> dict:
        """Get market health summary: order counts, total ISK, top opps."""
        orders_stats = await self._get_order_stats()
        top_arbitrage = await self._get_top_arbitrage(5)
        top_manufacturing = await self._get_top_manufacturing(5)
        hot_items = await self.get_hot_items(limit=10)
        region_summaries = await self._get_region_summaries()
        last_updated = await self._get_last_updated()

        return {
            "total_active_orders": orders_stats["total_orders"],
            "total_isk_in_orders": orders_stats["total_isk"],
            "buy_orders": orders_stats["buy_orders"],
            "sell_orders": orders_stats["sell_orders"],
            "top_arbitrage": top_arbitrage,
            "top_manufacturing": top_manufacturing,
            "hot_items": hot_items,
            "region_summaries": region_summaries,
            "last_updated": last_updated.isoformat() if last_updated else None,
        }

    async def get_trends(
        self,
        type_id: int,
        region_id: int,
    ) -> dict:
        """Get price trend data for Chart.js."""
        from app.models.market import MarketHistoryDaily
        from app.repositories.item import get_item_by_type_id
        from app.repositories.region import get_region_by_eve_id
        from sqlalchemy import select

        item = await get_item_by_type_id(self.db, type_id)
        region = await get_region_by_eve_id(self.db, region_id)

        result = await self.db.execute(
            select(MarketHistoryDaily)
            .where(
                MarketHistoryDaily.type_id == type_id,
                MarketHistoryDaily.region_id == region_id,
            )
            .order_by(MarketHistoryDaily.date.asc())
            .limit(180)
        )
        rows = result.scalars().all()

        return {
            "type_id": type_id,
            "item_name": item.name if item else f"#{type_id}",
            "region_id": region_id,
            "region_name": region.name if region else f"#{region_id}",
            "data_points": [
                {
                    "date": r.date.isoformat(),
                    "average_price": r.average,
                    "highest": r.highest,
                    "lowest": r.lowest,
                    "volume": r.volume,
                }
                for r in rows
            ],
        }

    async def get_hot_items(
        self,
        region_id: int | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Detect items with unusual volume/price movement (from cache)."""
        sql = text("""
        SELECT * FROM hot_item_cache hc
        ORDER BY hc.abs_change DESC
        LIMIT :limit
        """)
        result = await self.db.execute(sql, {"limit": limit})
        rows = result.fetchall()

        type_ids = {r.type_id for r in rows}
        region_ids = {r.region_id for r in rows}
        names = await self._resolve_names(type_ids, region_ids)

        return [
            {
                "type_id": r.type_id,
                "item_name": names["items"].get(r.type_id, f"#{r.type_id}"),
                "region_id": r.region_id,
                "region_name": names["regions"].get(r.region_id, f"#{r.region_id}"),
                "volume_change_pct": round(float(r.volume_change_pct or 0), 2),
                "current_vol": r.current_vol,
                "prev_vol": r.prev_vol,
                "buy_vol": r.buy_vol,
                "sell_vol": r.sell_vol,
                "prev_buy_vol": r.prev_buy_vol,
                "prev_sell_vol": r.prev_sell_vol,
            }
            for r in rows
        ]

    async def get_region_summaries(self) -> list[dict]:
        """Per-region order/volume stats."""
        return await self._get_region_summaries()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _get_order_stats(self) -> dict:
        sql = text("SELECT * FROM order_stats_cache WHERE id = 1")
        result = await self.db.execute(sql)
        row = result.fetchone()
        if row is None:
            return {"total_orders": 0, "buy_orders": 0, "sell_orders": 0, "total_isk": 0.0}
        return {
            "total_orders": row.total_orders,
            "buy_orders": row.buy_orders,
            "sell_orders": row.sell_orders,
            "total_isk": float(row.total_isk),
        }

    async def _get_top_arbitrage(self, limit: int) -> list[dict]:
        """Read top arbitrage from pre-computed cache table."""
        from sqlalchemy import desc, select
        from app.models.trading import ArbitrageOpportunity

        result = await self.db.execute(
            select(ArbitrageOpportunity)
            .order_by(desc(ArbitrageOpportunity.total_profit))
            .limit(limit)
        )
        rows = result.scalars().all()

        type_ids = {r.type_id for r in rows}
        region_ids = {r.buy_region_id for r in rows} | {r.sell_region_id for r in rows}
        names = await self._resolve_names(type_ids, region_ids)

        return [
            {
                "id": r.id, "type_id": r.type_id,
                "item_name": names["items"].get(r.type_id, f"#{r.type_id}"),
                "buy_region_id": r.buy_region_id,
                "buy_region_name": names["regions"].get(r.buy_region_id, f"#{r.buy_region_id}"),
                "sell_region_id": r.sell_region_id,
                "sell_region_name": names["regions"].get(r.sell_region_id, f"#{r.sell_region_id}"),
                "buy_price": r.buy_price, "sell_price": r.sell_price,
                "buy_volume": r.buy_volume, "sell_volume": r.sell_volume,
                "quantity": r.quantity,
                "profit_per_unit": r.profit_per_unit,
                "profit_margin": r.profit_margin,
                "total_profit": r.total_profit,
                "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            }
            for r in rows
        ]

    async def _get_top_manufacturing(self, limit: int) -> list[dict]:
        from app.services.manufacturing import ManufacturingAnalyzer

        analyzer = ManufacturingAnalyzer(self.db)
        return await analyzer.get_top_manufacturing(limit=limit)

    async def _get_region_summaries(self) -> list[dict]:
        sql = text("""
        SELECT rsc.*, r.name AS region_name
        FROM region_summary_cache rsc
        LEFT JOIN region r ON r.eve_region_id = rsc.region_id
        ORDER BY rsc.total_isk DESC
        """)
        result = await self.db.execute(sql)
        rows = result.fetchall()
        return [
            {
                "region_id": r.region_id,
                "region_name": r.region_name or f"#{r.region_id}",
                "order_count": r.order_count,
                "buy_count": r.buy_count,
                "sell_count": r.sell_count,
                "total_isk": float(r.total_isk),
            }
            for r in rows
        ]

    async def _get_last_updated(self) -> datetime.datetime | None:
        sql = text("SELECT MAX(fetched_at) FROM latest_fetch_cache")
        result = await self.db.execute(sql)
        row = result.fetchone()
        return row[0] if row else None

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
