"""Repository layer: data access for items."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item


async def get_item_by_type_id(db: AsyncSession, type_id: int) -> Item | None:
    result = await db.execute(select(Item).where(Item.type_id == type_id))
    return result.scalar_one_or_none()


async def search_items(
    db: AsyncSession, query: str, limit: int = 50
) -> list[Item]:
    """Search items by name (case-insensitive substring match)."""
    stmt = (
        select(Item)
        .where(Item.name.ilike(f"%{query}%"))
        .order_by(Item.name)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_items_by_type_ids(
    db: AsyncSession, type_ids: list[int]
) -> dict[int, Item]:
    result = await db.execute(
        select(Item).where(Item.type_id.in_(type_ids))
    )
    return {item.type_id: item for item in result.scalars().all()}
