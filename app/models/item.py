"""Item and MarketGroup models."""

from sqlalchemy import Boolean, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Item(Base, TimestampMixin):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    base_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    icon_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = ()

    def __repr__(self) -> str:
        return f"<Item type_id={self.type_id} name={self.name!r}>"


class MarketGroup(Base, TimestampMixin):
    __tablename__ = "market_group"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    eve_group_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_types: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<MarketGroup eve_group_id={self.eve_group_id} name={self.name!r}>"
