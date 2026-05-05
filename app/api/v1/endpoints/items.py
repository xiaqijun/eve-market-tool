"""Item search and detail endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories import item as item_repo
from app.schemas.item import ItemResponse, ItemSearchResponse

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/search", response_model=list[ItemSearchResponse])
async def search_items(
    q: str = Query(..., min_length=1, description="Search query (partial name)"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Search for items by name."""
    items = await item_repo.search_items(db, q, limit=limit)
    return [
        ItemSearchResponse(
            type_id=item.type_id,
            name=item.name,
            volume=item.volume,
            group_id=item.group_id,
        )
        for item in items
    ]


@router.get("/{type_id}", response_model=ItemResponse)
async def get_item(
    type_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific item by type_id."""
    item = await item_repo.get_item_by_type_id(db, type_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Item type_id={type_id} not found")
    return item
