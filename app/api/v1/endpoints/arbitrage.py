"""Arbitrage API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.arbitrage import (
    ArbitrageListResponse,
    ArbitrageOpportunityResponse,
    PriceComparisonResponse,
)
from app.services.arbitrage_engine import ArbitrageEngine

router = APIRouter(prefix="/arbitrage", tags=["arbitrage"])


@router.get("/opportunities", response_model=ArbitrageListResponse)
async def list_opportunities(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    min_profit_margin: float = Query(default=0.05, ge=0, le=10),
    min_profit_isk: float = Query(default=0, ge=0),
    region_id: int | None = Query(default=None),
    sort_by: str = Query(default="total_profit", pattern="^(total_profit|profit_margin)$"),
    db: AsyncSession = Depends(get_db),
):
    """List detected arbitrage opportunities."""
    engine = ArbitrageEngine(db)
    items = await engine.get_opportunities(
        limit=per_page,
        min_margin=min_profit_margin,
        min_profit=min_profit_isk,
        region_id=region_id,
        sort_by=sort_by,
    )

    # Simple in-memory pagination
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = items[start:end]

    return ArbitrageListResponse(
        page=page,
        per_page=per_page,
        total=total,
        items=[ArbitrageOpportunityResponse(**item) for item in page_items],
    )


@router.get("/opportunities/{opportunity_id}", response_model=ArbitrageOpportunityResponse)
async def get_opportunity(
    opportunity_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single arbitrage opportunity detail."""
    engine = ArbitrageEngine(db)
    items = await engine.get_opportunities(limit=200, min_margin=0)
    for item in items:
        if item["id"] == opportunity_id:
            return ArbitrageOpportunityResponse(**item)
    raise HTTPException(status_code=404, detail="Opportunity not found")


@router.get("/items/{type_id}/comparison", response_model=list[PriceComparisonResponse])
async def get_price_comparison(
    type_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get buy/sell price comparison for an item across all tracked regions."""
    engine = ArbitrageEngine(db)
    data = await engine.get_price_comparison(type_id)
    return [PriceComparisonResponse(**d) for d in data]


@router.post("/scan")
async def trigger_scan(
    min_profit_margin: float = Query(default=0.05, ge=0),
    min_profit_isk: float = Query(default=1_000_000, ge=0),
    top_n: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a fresh arbitrage scan using the latest order snapshots."""
    engine = ArbitrageEngine(db)
    results = await engine.scan(
        min_profit_margin=min_profit_margin,
        min_profit_isk=min_profit_isk,
        top_n=top_n,
    )
    return {
        "message": f"Scan complete. Found {len(results)} opportunities.",
        "count": len(results),
    }
