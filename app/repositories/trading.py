"""Repository layer: data access for trading."""

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading import StationTrade


async def get_trade_by_id(
    db: AsyncSession, trade_id: int
) -> StationTrade | None:
    result = await db.execute(
        select(StationTrade).where(StationTrade.id == trade_id)
    )
    return result.scalar_one_or_none()


async def get_trades_by_user(
    db: AsyncSession,
    user_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[StationTrade]:
    stmt = select(StationTrade)
    if user_id is not None:
        stmt = stmt.where(StationTrade.user_id == user_id)
    if status is not None:
        stmt = stmt.where(StationTrade.status == status)
    stmt = stmt.order_by(desc(StationTrade.created_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_trade(
    db: AsyncSession, **kwargs
) -> StationTrade:
    trade = StationTrade(**kwargs)
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    return trade


async def update_trade(
    db: AsyncSession, trade_id: int, **kwargs
) -> StationTrade | None:
    trade = await get_trade_by_id(db, trade_id)
    if trade is None:
        return None
    for key, value in kwargs.items():
        if value is not None:
            setattr(trade, key, value)
    await db.commit()
    await db.refresh(trade)
    return trade


async def get_trade_summary(
    db: AsyncSession, user_id: int | None = None
) -> dict:
    stmt = select(
        func.count(StationTrade.id).label("total"),
        func.count(StationTrade.id).filter(StationTrade.status == "active").label("active"),
        func.count(StationTrade.id).filter(StationTrade.status == "completed").label("completed"),
        func.coalesce(func.sum(StationTrade.net_profit), 0).label("profit"),
        func.coalesce(
            func.sum(StationTrade.buy_price * StationTrade.quantity)
            .filter(StationTrade.status != "cancelled"),
            0,
        ).label("investment"),
    )
    if user_id is not None:
        stmt = stmt.where(StationTrade.user_id == user_id)
    result = await db.execute(stmt)
    row = result.fetchone()
    return {
        "total_trades": row.total or 0,
        "active_trades": row.active or 0,
        "completed_trades": row.completed or 0,
        "total_profit": float(row.profit or 0),
        "total_investment": float(row.investment or 0),
    }
