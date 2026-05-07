"""Dashboard API endpoints."""

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
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


@router.get("/trends/{type_id}/chart", response_class=HTMLResponse)
async def get_trends_chart(
    type_id: int,
    region_id: int = Query(default=10000002),
    db: AsyncSession = Depends(get_db),
):
    """Price trend as an HTML snippet for htmx + Chart.js rendering."""
    service = DashboardService(db)
    data = await service.get_trends(type_id, region_id)
    trend_json = json.dumps(data, ensure_ascii=False)
    item_name = data.get("item_name", f"#{type_id}")
    region_name = data.get("region_name", "")
    points = len(data.get("data_points", []))

    html = f"""
    <div style="margin-bottom:0.5rem;font-family:var(--font-mono);font-size:0.8rem;color:var(--text-dim);">
        {item_name} · {region_name} · {points} 个数据点
    </div>
    <div style="position:relative;height:350px;">
        <canvas id="priceChart" data-trend='{trend_json}'></canvas>
    </div>
    <script>
        (function() {{
            const el = document.getElementById('priceChart');
            if (el && window.initPriceChart) {{
                window.initPriceChart('priceChart', {trend_json});
            }}
        }})();
    </script>
    """
    return HTMLResponse(html)


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
