"""Region-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class RegionResponse(BaseModel):
    """Public response for a region."""

    id: int
    eve_region_id: int
    name: str
    station_id: int | None = None
    solar_system_id: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
