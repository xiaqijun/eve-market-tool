"""Dashboard API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.dashboard import (
    DashboardOverviewResponse,
    HotItemResponse,
    PricePoint,
    PriceTrendResponse,
    RegionSummary,
)
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_overview(
    db: AsyncSession = Depends(get_db),
):
    """Market health summary."""
    service = DashboardService(db)
    data = await service.get_overview()
    return DashboardOverviewResponse(**data)


@router.get("/trends/{type_id}", response_model=PriceTrendResponse)
async def get_trends(
    type_id: int,
    region_id: int = Query(default=10000002),
    db: AsyncSession = Depends(get_db),
):
    """Price trend data for a specific item in a region (for charts)."""
    service = DashboardService(db)
    data = await service.get_trends(type_id, region_id)
    return PriceTrendResponse(**data)


@router.get("/hot-items", response_model=list[HotItemResponse])
async def get_hot_items(
    region_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Items with unusual volume activity."""
    service = DashboardService(db)
    items = await service.get_hot_items(region_id=region_id, limit=limit)
    return [HotItemResponse(**item) for item in items]


@router.get("/region-summary", response_model=list[RegionSummary])
async def get_region_summary(
    db: AsyncSession = Depends(get_db),
):
    """Per-region order and volume statistics."""
    service = DashboardService(db)
    summaries = await service.get_region_summaries()
    return [RegionSummary(**s) for s in summaries]
