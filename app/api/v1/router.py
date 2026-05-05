"""Aggregates all v1 API routers."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    alerts,
    arbitrage,
    auth,
    dashboard,
    items,
    manufacturing,
    regions,
    station_trading,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(items.router)
api_v1_router.include_router(regions.router)
api_v1_router.include_router(arbitrage.router)
api_v1_router.include_router(station_trading.router)
api_v1_router.include_router(manufacturing.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(alerts.router)
api_v1_router.include_router(auth.router)
