"""Manufacturing profitability analysis service.

Compares blueprint material costs against market prices to determine
whether manufacturing an item is profitable.
"""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.manufacturing import BlueprintMaterial, ManufacturingAnalysis

logger = logging.getLogger(__name__)


class ManufacturingAnalyzer:
    """Analyzes blueprint manufacturing profitability."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def analyze_blueprint(
        self,
        blueprint_type_id: int,
        region_id: int = 10000002,
        quantity: int = 1,
        facility_tax: float = 0.0,
    ) -> dict:
        """Calculate manufacturing cost and estimated profit.

        Returns a dict with all cost components and profit estimates.
        """
        # 1. Get blueprint materials
        from sqlalchemy import select
        from app.models.manufacturing import Blueprint
        from app.repositories.item import get_item_by_type_id

        bp_result = await self.db.execute(
            select(Blueprint).where(Blueprint.blueprint_type_id == blueprint_type_id)
        )
        blueprint = bp_result.scalar_one_or_none()

        if blueprint is None:
            raise ValueError(f"Blueprint {blueprint_type_id} not found in database")

        mat_result = await self.db.execute(
            select(BlueprintMaterial).where(
                BlueprintMaterial.blueprint_id == blueprint.id
            )
        )
        materials = mat_result.scalars().all()

        if not materials:
            raise ValueError(f"Blueprint {blueprint_type_id} has no materials")

        # 2. Get material market prices (cheapest sell order per material)
        materials_cost = 0.0
        material_details = []

        for mat in materials:
            price, vol = await self._get_cheapest_sell_price(
                mat.material_type_id, region_id
            )
            unit_price = price if price else 0
            total_mat_cost = unit_price * mat.quantity * quantity
            materials_cost += total_mat_cost
            material_name = await self._resolve_item_name(mat.material_type_id)
            material_details.append(
                {
                    "material_type_id": mat.material_type_id,
                    "material_name": material_name,
                    "quantity_per_unit": mat.quantity,
                    "total_quantity": mat.quantity * quantity,
                    "unit_price": unit_price,
                    "total_cost": total_mat_cost,
                }
            )

        # 3. Job installation fee is a percentage of total material cost
        # (simplified; the actual formula uses system cost index)
        job_installation_fee = materials_cost * 0.01 * (1 + facility_tax)

        # 4. Total production cost
        total_cost = materials_cost + job_installation_fee

        # 5. Market prices for the product
        buy_price, _ = await self._get_highest_buy_price(
            blueprint.product_type_id, region_id
        )
        sell_price, _ = await self._get_cheapest_sell_price(
            blueprint.product_type_id, region_id
        )

        product_name = await self._resolve_item_name(blueprint.product_type_id)

        # 6. Profit estimates
        profit_sell = (sell_price or buy_price or 0) * quantity - total_cost
        margin_sell = (
            profit_sell / total_cost if total_cost > 0 and profit_sell else 0
        )

        # Persist
        analysis = ManufacturingAnalysis(
            product_type_id=blueprint.product_type_id,
            blueprint_type_id=blueprint_type_id,
            region_id=region_id,
            quantity=quantity,
            materials_cost=materials_cost,
            job_installation_fee=job_installation_fee,
            total_production_cost=total_cost,
            market_sell_price=sell_price or 0,
            market_buy_price=buy_price or 0,
            estimated_profit=profit_sell,
            profit_margin=margin_sell,
            calculated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.db.add(analysis)
        await self.db.commit()

        return {
            "id": analysis.id,
            "blueprint_type_id": blueprint_type_id,
            "product_type_id": blueprint.product_type_id,
            "product_name": product_name,
            "region_id": region_id,
            "quantity": quantity,
            "materials": material_details,
            "materials_cost": materials_cost,
            "job_installation_fee": job_installation_fee,
            "total_production_cost": total_cost,
            "market_sell_price": sell_price or buy_price or 0,
            "market_buy_price": buy_price or 0,
            "estimated_profit": profit_sell,
            "profit_margin": margin_sell,
            "calculated_at": analysis.calculated_at.isoformat(),
        }

    async def get_top_manufacturing(
        self,
        region_id: int = 10000002,
        limit: int = 50,
    ) -> list[dict]:
        """Get the most profitable manufacturing analyses for a region."""
        from sqlalchemy import desc, select

        result = await self.db.execute(
            select(ManufacturingAnalysis)
            .where(ManufacturingAnalysis.region_id == region_id)
            .order_by(desc(ManufacturingAnalysis.profit_margin))
            .limit(limit)
        )
        rows = result.scalars().all()

        analyses = []
        for r in rows:
            name = await self._resolve_item_name(r.product_type_id)
            analyses.append(
                {
                    "id": r.id,
                    "blueprint_type_id": r.blueprint_type_id,
                    "product_type_id": r.product_type_id,
                    "product_name": name,
                    "region_id": r.region_id,
                    "quantity": r.quantity,
                    "materials_cost": r.materials_cost,
                    "total_production_cost": r.total_production_cost,
                    "market_sell_price": r.market_sell_price,
                    "estimated_profit": r.estimated_profit,
                    "profit_margin": r.profit_margin,
                    "calculated_at": r.calculated_at.isoformat(),
                }
            )
        return analyses

    async def get_analyses(
        self,
        region_id: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List saved manufacturing analyses."""
        from sqlalchemy import desc, select

        stmt = select(ManufacturingAnalysis).order_by(
            desc(ManufacturingAnalysis.calculated_at)
        )
        if region_id is not None:
            stmt = stmt.where(ManufacturingAnalysis.region_id == region_id)
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        analyses = []
        for r in rows:
            name = await self._resolve_item_name(r.product_type_id)
            analyses.append(
                {
                    "id": r.id,
                    "blueprint_type_id": r.blueprint_type_id,
                    "product_type_id": r.product_type_id,
                    "product_name": name,
                    "region_id": r.region_id,
                    "quantity": r.quantity,
                    "materials_cost": r.materials_cost,
                    "total_production_cost": r.total_production_cost,
                    "market_sell_price": r.market_sell_price,
                    "estimated_profit": r.estimated_profit,
                    "profit_margin": r.profit_margin,
                    "calculated_at": r.calculated_at.isoformat(),
                }
            )
        return analyses

    # ------------------------------------------------------------------
    # Internal price lookups
    # ------------------------------------------------------------------

    async def _get_cheapest_sell_price(
        self, type_id: int, region_id: int
    ) -> tuple[float | None, int]:
        """Get cheapest sell order price and volume for a type in a region."""
        sql = text("""
        SELECT price, volume_remain
        FROM market_order_snapshot mos
        JOIN latest_fetch_cache lc
            ON mos.fetched_at = lc.fetched_at AND mos.region_id = lc.region_id
        WHERE mos.type_id = :type_id
          AND mos.region_id = :region_id
          AND mos.is_buy_order = FALSE
          AND mos.volume_remain >= 1
        ORDER BY mos.price ASC
        LIMIT 1
        """)
        result = await self.db.execute(
            sql, {"type_id": type_id, "region_id": region_id}
        )
        row = result.fetchone()
        return (row.price, row.volume_remain) if row else (None, 0)

    async def _get_highest_buy_price(
        self, type_id: int, region_id: int
    ) -> tuple[float | None, int]:
        """Get highest buy order price and volume for a type in a region."""
        sql = text("""
        SELECT price, volume_remain
        FROM market_order_snapshot mos
        JOIN latest_fetch_cache lc
            ON mos.fetched_at = lc.fetched_at AND mos.region_id = lc.region_id
        WHERE mos.type_id = :type_id
          AND mos.region_id = :region_id
          AND mos.is_buy_order = TRUE
          AND mos.volume_remain >= 1
        ORDER BY mos.price DESC
        LIMIT 1
        """)
        result = await self.db.execute(
            sql, {"type_id": type_id, "region_id": region_id}
        )
        row = result.fetchone()
        return (row.price, row.volume_remain) if row else (None, 0)

    async def _resolve_item_name(self, type_id: int) -> str:
        from sqlalchemy import select
        from app.models.item import Item

        result = await self.db.execute(
            select(Item.name).where(Item.type_id == type_id)
        )
        row = result.fetchone()
        return row.name if row else f"Unknown #{type_id}"
