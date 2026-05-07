"""Authentication endpoints: EVE SSO login / callback / logout."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import EveSsoClient, JwtHandler, hash_token
from app.models.user import User
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["auth"])
sso_client = EveSsoClient()


@router.get("/login")
async def login():
    """Redirect to EVE Online SSO for authentication."""
    url = sso_client.get_authorization_url()
    return RedirectResponse(url=url)


@router.get("/callback")
async def callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """EVE SSO callback — exchange code for tokens, create/update user."""
    token_data = await sso_client.exchange_code(code)
    if token_data is None:
        raise HTTPException(status_code=400, detail="Token exchange failed")

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="No access token received")

    # Validate the EVE JWT to get character info
    payload = await sso_client.validate_eve_jwt(access_token)
    if payload is None:
        raise HTTPException(status_code=400, detail="JWT validation failed")

    character_id = int(payload.get("sub", "").replace("CHARACTER:EVE:", ""))
    character_name = payload.get("name", "Unknown")

    # Upsert user
    result = await db.execute(
        select(User).where(User.character_id == character_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            character_id=character_id,
            character_name=character_name,
        )
        db.add(user)

    user.access_token_hash = hash_token(access_token)
    if refresh_token:
        user.refresh_token_hash = hash_token(refresh_token)
    user.last_login_at = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    )
    await db.commit()

    # Issue local session JWT
    session_token = JwtHandler.create_session_token(character_id, character_name)

    return {
        "message": f"Authenticated as {character_name}",
        "character_id": character_id,
        "character_name": character_name,
        "token": session_token,
    }


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Get current user info."""
    return {
        "character_id": user.character_id,
        "character_name": user.character_name,
        "corporation_id": user.corporation_id,
        "alliance_id": user.alliance_id,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


@router.post("/logout")
async def logout():
    """Logout (clear local session)."""
    return {"message": "Logged out"}
