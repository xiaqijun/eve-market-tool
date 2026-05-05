"""Region list and detail endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories import region as region_repo
from app.schemas.region import RegionResponse

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("/", response_model=list[RegionResponse])
async def list_regions(
    db: AsyncSession = Depends(get_db),
):
    """List all tracked trade hub regions."""
    regions = await region_repo.get_all_active_regions(db)
    return regions
