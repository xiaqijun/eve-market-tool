"""User model for EVE SSO authenticated users."""

import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    character_name: Mapped[str] = mapped_column(String(200), nullable=False)
    corporation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alliance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    access_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_expires_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )
    last_login_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<User character_id={self.character_id} name={self.character_name!r}>"
