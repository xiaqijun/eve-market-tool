"""Trading models: station trades and arbitrage opportunities."""

import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StationTrade(Base):
    """A tracked buy-and-resell trade at a single station."""

    __tablename__ = "station_trade"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=True, index=True
    )
    type_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    region_id: Mapped[int] = mapped_column(Integer, nullable=False)
    station_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    buy_order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sell_order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    buy_price: Mapped[float] = mapped_column(Float, nullable=False)
    sell_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    volume_remaining: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="scouting", nullable=False
    )
    net_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<StationTrade id={self.id} type_id={self.type_id} "
            f"status={self.status} profit={self.net_profit}>"
        )


class ArbitrageOpportunity(Base):
    """A detected cross-region arbitrage opportunity."""

    __tablename__ = "arbitrage_opportunity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    buy_region_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sell_region_id: Mapped[int] = mapped_column(Integer, nullable=False)
    buy_price: Mapped[float] = mapped_column(Float, nullable=False)
    sell_price: Mapped[float] = mapped_column(Float, nullable=False)
    buy_volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sell_volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    profit_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    profit_margin: Mapped[float] = mapped_column(Float, nullable=False)
    total_profit: Mapped[float] = mapped_column(Float, nullable=False)
    detected_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "type_id",
            "buy_region_id",
            "sell_region_id",
            "detected_at",
            name="uq_arb_opportunity",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Arbitrage type_id={self.type_id} "
            f"{self.buy_region_id}→{self.sell_region_id} "
            f"margin={self.profit_margin:.2%} profit={self.total_profit:.2f}>"
        )
