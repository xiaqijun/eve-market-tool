"""Dashboard-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.arbitrage import ArbitrageOpportunityResponse
from app.schemas.manufacturing import ManufacturingSummary


class PricePoint(BaseModel):
    date: str
    average_price: float | None = None
    highest: float | None = None
    lowest: float | None = None
    volume: int | None = None


class PriceTrendResponse(BaseModel):
    type_id: int
    item_name: str
    region_id: int
    region_name: str
    data_points: list[PricePoint]


class RegionSummary(BaseModel):
    region_id: int
    region_name: str
    order_count: int
    buy_count: int
    sell_count: int
    total_isk: float


class HotItemResponse(BaseModel):
    type_id: int
    item_name: str
    region_id: int
    region_name: str
    volume_change_pct: float
    current_vol: int
    prev_vol: int
    buy_vol: int | None = None
    sell_vol: int | None = None
    prev_buy_vol: int | None = None
    prev_sell_vol: int | None = None


class DashboardOverviewResponse(BaseModel):
    total_active_orders: int
    total_isk_in_orders: float
    buy_orders: int
    sell_orders: int
    top_arbitrage: list[ArbitrageOpportunityResponse]
    top_manufacturing: list[ManufacturingSummary]
    hot_items: list[HotItemResponse]
    region_summaries: list[RegionSummary]
    last_updated: str | None = None
