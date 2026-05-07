"""Alert models: price alerts."""

import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PriceAlert(Base):
    """User-defined price alert."""

    __tablename__ = "price_alert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=False, index=True
    )
    type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    region_id: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[str] = mapped_column(String(10), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_triggered: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    __table_args__ = ()

    def __repr__(self) -> str:
        return (
            f"<PriceAlert type_id={self.type_id} "
            f"condition={self.condition} threshold={self.threshold}>"
        )
