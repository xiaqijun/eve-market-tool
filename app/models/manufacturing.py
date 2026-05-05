"""Manufacturing models: blueprints, materials, and profitability analyses."""

import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Blueprint(Base):
    """Blueprint production information."""

    __tablename__ = "blueprint"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blueprint_type_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, index=True
    )
    product_type_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    manufacturing_time: Mapped[int] = mapped_column(Integer, nullable=False)
    max_production_limit: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    activity_type: Mapped[str] = mapped_column(
        String(20), default="manufacturing", nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Blueprint blueprint_type_id={self.blueprint_type_id} "
            f"product_type_id={self.product_type_id}>"
        )


class BlueprintMaterial(Base):
    """Materials required per blueprint."""

    __tablename__ = "blueprint_material"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blueprint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("blueprint.id", ondelete="CASCADE"), nullable=False
    )
    material_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<BlueprintMaterial blueprint_id={self.blueprint_id} "
            f"material_type_id={self.material_type_id} qty={self.quantity}>"
        )


class ManufacturingAnalysis(Base):
    """Saved manufacturing profitability calculation."""

    __tablename__ = "manufacturing_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=True, index=True
    )
    product_type_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    blueprint_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    region_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    materials_cost: Mapped[float] = mapped_column(Float, nullable=False)
    job_installation_fee: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    total_production_cost: Mapped[float] = mapped_column(Float, nullable=False)
    market_sell_price: Mapped[float] = mapped_column(Float, nullable=False)
    market_buy_price: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_profit: Mapped[float] = mapped_column(Float, nullable=False)
    profit_margin: Mapped[float] = mapped_column(Float, nullable=False)
    calculated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ManufacturingAnalysis product_type_id={self.product_type_id} "
            f"profit={self.estimated_profit:.2f} margin={self.profit_margin:.2%}>"
        )
