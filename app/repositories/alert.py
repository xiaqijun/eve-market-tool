"""Repository layer: data access for price alerts."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import PriceAlert


async def get_alerts_by_user(
    db: AsyncSession,
    user_id: int,
    active_only: bool = False,
) -> list[PriceAlert]:
    stmt = select(PriceAlert).where(PriceAlert.user_id == user_id)
    if active_only:
        stmt = stmt.where(PriceAlert.is_active == True)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_alert_by_id(
    db: AsyncSession, alert_id: int
) -> PriceAlert | None:
    result = await db.execute(
        select(PriceAlert).where(PriceAlert.id == alert_id)
    )
    return result.scalar_one_or_none()


async def create_alert(
    db: AsyncSession, **kwargs
) -> PriceAlert:
    alert = PriceAlert(**kwargs)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


async def update_alert(
    db: AsyncSession, alert_id: int, **kwargs
) -> PriceAlert | None:
    alert = await get_alert_by_id(db, alert_id)
    if alert is None:
        return None
    for key, value in kwargs.items():
        if value is not None:
            setattr(alert, key, value)
    await db.commit()
    await db.refresh(alert)
    return alert
