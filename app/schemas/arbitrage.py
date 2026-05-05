"""Arbitrage-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ArbitrageOpportunityResponse(BaseModel):
    id: int
    type_id: int
    item_name: str
    buy_region_id: int
    buy_region_name: str
    sell_region_id: int
    sell_region_name: str
    buy_price: float
    sell_price: float
    buy_volume: int
    sell_volume: int
    quantity: int
    profit_per_unit: float
    profit_margin: float
    total_profit: float
    detected_at: str | None = None


class ArbitrageListResponse(BaseModel):
    page: int
    per_page: int
    total: int
    items: list[ArbitrageOpportunityResponse]


class PriceComparisonResponse(BaseModel):
    region_id: int
    region_name: str
    min_sell_price: float | None = None
    max_buy_price: float | None = None
    sell_volume: int = 0
    buy_volume: int = 0
