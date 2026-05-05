"""FastAPI shared dependencies."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

# Re-export get_db as a convenient import
__all__ = ["get_db"]
