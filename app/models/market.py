"""Market data models: order snapshots, daily history, and universe prices."""

import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MarketOrderSnapshot(Base):
    """Point-in-time snapshot of a single market order."""

    __tablename__ = "market_order_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    region_id: Mapped[int] = mapped_column(Integer, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    system_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_buy_order: Mapped[bool] = mapped_column(Boolean, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    volume_remain: Mapped[int] = mapped_column(BigInteger, nullable=False)
    volume_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_volume: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    range: Mapped[str] = mapped_column(String(50), default="station", nullable=False)
    issued: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("order_id", "fetched_at", name="uq_order_fetch"),
    )

    def __repr__(self) -> str:
        direction = "buy" if self.is_buy_order else "sell"
        return (
            f"<MarketOrder order_id={self.order_id} "
            f"type_id={self.type_id} {direction} "
            f"price={self.price:.2f} vol={self.volume_remain}>"
        )


class MarketHistoryDaily(Base):
    """Daily OHLCV market history for an item in a region."""

    __tablename__ = "market_history_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    region_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    average: Mapped[float | None] = mapped_column(Float, nullable=True)
    highest: Mapped[float | None] = mapped_column(Float, nullable=True)
    lowest: Mapped[float | None] = mapped_column(Float, nullable=True)
    order_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "type_id", "region_id", "date", name="uq_history_type_region_date"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<MarketHistory type_id={self.type_id} region={self.region_id} "
            f"date={self.date} avg={self.average}>"
        )


class MarketPrice(Base):
    """Universe-wide average/adjusted prices from /markets/prices/."""

    __tablename__ = "market_price"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, index=True
    )
    adjusted_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<MarketPrice type_id={self.type_id} "
            f"avg={self.average_price} adj={self.adjusted_price}>"
        )
