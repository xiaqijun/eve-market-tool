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
    offset = (page - 1) * per_page
    items, total = await engine.get_opportunities(
        limit=per_page,
        offset=offset,
        min_margin=min_profit_margin,
        min_profit=min_profit_isk,
        region_id=region_id,
        sort_by=sort_by,
    )

    return ArbitrageListResponse(
        page=page,
        per_page=per_page,
        total=total,
        items=[ArbitrageOpportunityResponse(**item) for item in items],
    )


@router.get("/opportunities/{opportunity_id}", response_model=ArbitrageOpportunityResponse)
async def get_opportunity(
    opportunity_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single arbitrage opportunity detail."""
    from sqlalchemy import select
    from app.models.trading import ArbitrageOpportunity
    from app.repositories.item import get_item_by_type_id
    from app.repositories.region import get_region_by_eve_id

    result = await db.execute(
        select(ArbitrageOpportunity).where(ArbitrageOpportunity.id == opportunity_id)
    )
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    item = await get_item_by_type_id(db, r.type_id)
    buy_region = await get_region_by_eve_id(db, r.buy_region_id)
    sell_region = await get_region_by_eve_id(db, r.sell_region_id)

    return ArbitrageOpportunityResponse(
        id=r.id,
        type_id=r.type_id,
        item_name=item.name if item else f"#{r.type_id}",
        buy_region_id=r.buy_region_id,
        buy_region_name=buy_region.name if buy_region else f"#{r.buy_region_id}",
        sell_region_id=r.sell_region_id,
        sell_region_name=sell_region.name if sell_region else f"#{r.sell_region_id}",
        buy_price=r.buy_price,
        sell_price=r.sell_price,
        buy_volume=r.buy_volume,
        sell_volume=r.sell_volume,
        quantity=r.quantity,
        profit_per_unit=r.profit_per_unit,
        profit_margin=r.profit_margin,
        total_profit=r.total_profit,
        detected_at=r.detected_at.isoformat() if r.detected_at else None,
    )


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
