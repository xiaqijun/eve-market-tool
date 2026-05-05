"""Price alert API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories import alert as alert_repo
from pydantic import BaseModel, Field

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


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(
    active_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    """List all price alerts."""
    # For now, list all alerts (user filter when auth is active)
    from app.models.alert import PriceAlert
    from sqlalchemy import select

    stmt = select(PriceAlert).order_by(PriceAlert.created_at.desc())
    if active_only:
        stmt = stmt.where(PriceAlert.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    return [
        AlertResponse(
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
        for a in alerts
    ]


@router.post("/", response_model=AlertResponse)
async def create_alert(
    request: AlertCreate,
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
        user_id=None,  # no auth yet
    )
    return AlertResponse(
        id=alert.id, user_id=alert.user_id,
        type_id=alert.type_id, region_id=alert.region_id,
        condition=alert.condition, threshold=alert.threshold,
        is_active=alert.is_active,
        last_triggered=alert.last_triggered.isoformat() if alert.last_triggered else None,
        created_at=alert.created_at.isoformat() if alert.created_at else None,
    )


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    request: AlertUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update or disable a price alert."""
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    alert = await alert_repo.update_alert(db, alert_id, **updates)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse(
        id=alert.id, user_id=alert.user_id,
        type_id=alert.type_id, region_id=alert.region_id,
        condition=alert.condition, threshold=alert.threshold,
        is_active=alert.is_active,
        last_triggered=alert.last_triggered.isoformat() if alert.last_triggered else None,
        created_at=alert.created_at.isoformat() if alert.created_at else None,
    )


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a price alert."""
    alert = await alert_repo.get_alert_by_id(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.delete(alert)
    await db.commit()
    return {"message": "Alert deleted"}
