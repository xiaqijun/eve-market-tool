"""FastAPI shared dependencies."""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import JwtHandler
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the Bearer token, return the authenticated User.

    Raises 401 if token is missing, invalid, expired, or user not found.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = JwtHandler.decode_session_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    character_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.character_id == character_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of raising 401."""
    if credentials is None:
        return None

    payload = JwtHandler.decode_session_token(credentials.credentials)
    if payload is None:
        return None

    character_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.character_id == character_id))
    return result.scalar_one_or_none()


__all__ = ["get_db", "get_current_user", "get_current_user_optional"]
