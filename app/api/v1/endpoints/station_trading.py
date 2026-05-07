"""Station trading API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories import trading as trading_repo
from app.schemas.trading import (
    StationTradingOpportunityResponse,
    TradeCreateRequest,
    TradeResponse,
    TradeSummaryResponse,
    TradeUpdateRequest,
)
from app.services.station_trading import StationTradingService

router = APIRouter(prefix="/trading", tags=["trading"])


@router.get("/opportunities", response_model=list[StationTradingOpportunityResponse])
async def find_opportunities(
    region_id: int = Query(..., description="EVE region ID (e.g., 10000002 for Jita)"),
    station_id: int | None = Query(default=None),
    min_margin: float = Query(default=0.10, ge=0),
    max_investment: float | None = Query(default=None, ge=0),
    sort_by: str = Query(default="potential_profit", pattern="^(potential_profit|margin)$"),
    limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Find station trading opportunities with buy/sell spreads."""
    service = StationTradingService(db)
    results = await service.find_opportunities(
        region_id=region_id,
        station_id=station_id,
        min_margin=min_margin,
        max_investment=max_investment,
        sort_by=sort_by,
        limit=limit,
    )
    return [
        StationTradingOpportunityResponse(
            type_id=o.type_id,
            item_name=o.item_name,
            region_id=o.region_id,
            station_id=o.station_id,
            buy_price=o.buy_price,
            sell_price=o.sell_price,
            spread=o.spread,
            margin=o.margin,
            buy_volume=o.buy_volume,
            sell_volume=o.sell_volume,
            potential_quantity=o.potential_quantity,
            potential_profit=o.potential_profit,
        )
        for o in results
    ]


@router.get("/opportunities/{type_id}")
async def get_opportunity_detail(
    type_id: int,
    region_id: int = Query(..., description="EVE region ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed spread for a specific item in a region."""
    service = StationTradingService(db)
    result = await service.get_opportunity_detail(type_id, region_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No trading opportunity found for this item")
    return result


# ------------------------------------------------------------------
# Tracked trades CRUD
# ------------------------------------------------------------------


@router.get("/trades", response_model=list[TradeResponse])
async def list_trades(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's tracked trades."""
    trades = await trading_repo.get_trades_by_user(
        db, user_id=user.id, status=status, limit=limit, offset=offset
    )
    return trades


@router.post("/trades", response_model=TradeResponse)
async def create_trade(
    request: TradeCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start tracking a new station trade."""
    trade = await trading_repo.create_trade(
        db,
        type_id=request.type_id,
        region_id=request.region_id,
        station_id=request.station_id,
        buy_price=request.buy_price,
        sell_price=request.sell_price,
        quantity=request.quantity,
        volume_remaining=request.quantity,
        notes=request.notes,
        status="active",
        user_id=user.id,
    )
    return trade


@router.put("/trades/{trade_id}", response_model=TradeResponse)
async def update_trade(
    trade_id: int,
    request: TradeUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a tracked trade's status or details."""
    trade = await trading_repo.get_trade_by_id(db, trade_id)
    if trade is None or trade.user_id != user.id:
        raise HTTPException(status_code=404, detail="Trade not found")

    update_data = {k: v for k, v in request.model_dump().items() if v is not None}
    trade = await trading_repo.update_trade(db, trade_id, **update_data)
    return trade


@router.get("/summary", response_model=TradeSummaryResponse)
async def get_trade_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get profit/loss summary for current user's tracked trades."""
    summary = await trading_repo.get_trade_summary(db, user_id=user.id)
    return TradeSummaryResponse(**summary)
