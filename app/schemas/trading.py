"""Trading-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class StationTradingOpportunityResponse(BaseModel):
    type_id: int
    item_name: str
    region_id: int
    station_id: int
    buy_price: float
    sell_price: float
    spread: float
    margin: float
    buy_volume: int
    sell_volume: int
    potential_quantity: int
    potential_profit: float


class TradeCreateRequest(BaseModel):
    type_id: int
    region_id: int
    station_id: int
    buy_price: float
    sell_price: float
    quantity: int
    notes: str | None = None


class TradeUpdateRequest(BaseModel):
    status: str | None = None
    volume_remaining: int | None = None
    sell_price: float | None = None
    net_profit: float | None = None
    profit_margin: float | None = None
    notes: str | None = None


class TradeResponse(BaseModel):
    id: int
    user_id: int | None = None
    type_id: int
    region_id: int
    station_id: int
    buy_order_id: int | None = None
    sell_order_id: int | None = None
    buy_price: float
    sell_price: float
    quantity: int
    volume_remaining: int
    status: str
    net_profit: float | None = None
    profit_margin: float | None = None
    notes: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class TradeSummaryResponse(BaseModel):
    total_trades: int
    active_trades: int
    completed_trades: int
    total_profit: float
    total_investment: float
