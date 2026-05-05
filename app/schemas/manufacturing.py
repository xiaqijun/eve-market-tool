"""Manufacturing-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class MaterialDetail(BaseModel):
    material_type_id: int
    material_name: str
    quantity_per_unit: int
    total_quantity: int
    unit_price: float
    total_cost: float


class ManufacturingAnalysisRequest(BaseModel):
    blueprint_type_id: int
    region_id: int = 10000002
    quantity: int = 1
    facility_tax: float = 0.0


class ManufacturingAnalysisResponse(BaseModel):
    id: int
    blueprint_type_id: int
    product_type_id: int
    product_name: str
    region_id: int
    quantity: int
    materials: list[MaterialDetail] = []
    materials_cost: float
    job_installation_fee: float
    total_production_cost: float
    market_sell_price: float
    market_buy_price: float
    estimated_profit: float
    profit_margin: float
    calculated_at: str


class ManufacturingSummary(BaseModel):
    id: int
    blueprint_type_id: int
    product_type_id: int
    product_name: str
    region_id: int
    quantity: int
    materials_cost: float
    total_production_cost: float
    market_sell_price: float
    estimated_profit: float
    profit_margin: float
    calculated_at: str
