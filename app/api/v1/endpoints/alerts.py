"""Price alert API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.alert import PriceAlert
from app.models.user import User
from app.repositories import alert as alert_repo

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertCreate(BaseModel):
    type_id: int
    region_id: int
    condition: str = Field(pattern="^(above|below)$")
    threshold: float
    is_active: bool = True


class AlertUpdate(BaseModel):
    condition: str | None = Field(default=None, pattern="^(above|below)$")
    threshold: float | None = None
    is_active: bool | None = None


class AlertResponse(BaseModel):
    id: int
    user_id: int | None = None
    type_id: int
    region_id: int
    condition: str
    threshold: float
    is_active: bool
    last_triggered: str | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


def _alert_response(a: PriceAlert) -> AlertResponse:
    return AlertResponse(
        id=a.id,
        user_id=a.user_id,
        type_id=a.type_id,
        region_id=a.region_id,
        condition=a.condition,
        threshold=a.threshold,
        is_active=a.is_active,
        last_triggered=a.last_triggered.isoformat() if a.last_triggered else None,
        created_at=a.created_at.isoformat() if a.created_at else None,
    )


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(
    active_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's price alerts."""
    alerts = await alert_repo.get_alerts_by_user(
        db, user_id=user.id, active_only=active_only
    )
    return [_alert_response(a) for a in alerts]


@router.post("/", response_model=AlertResponse)
async def create_alert(
    request: AlertCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new price alert."""
    alert = await alert_repo.create_alert(
        db,
        type_id=request.type_id,
        region_id=request.region_id,
        condition=request.condition,
        threshold=request.threshold,
        is_active=request.is_active,
        user_id=user.id,
    )
    return _alert_response(alert)


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    request: AlertUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update or disable a price alert."""
    alert = await alert_repo.get_alert_by_id(db, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status_code=404, detail="Alert not found")

    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    alert = await alert_repo.update_alert(db, alert_id, **updates)
    return _alert_response(alert)


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a price alert."""
    alert = await alert_repo.get_alert_by_id(db, alert_id)
    if alert is None or alert.user_id != user.id:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.delete(alert)
    await db.commit()
    return {"message": "Alert deleted"}
