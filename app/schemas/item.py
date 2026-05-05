"""Item-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class ItemResponse(BaseModel):
    """Public response for an item."""

    id: int
    type_id: int
    name: str
    description: str | None = None
    group_id: int | None = None
    category_id: int | None = None
    volume: float | None = None
    base_price: float | None = None
    icon_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ItemSearchResponse(BaseModel):
    """Search result item."""

    type_id: int
    name: str
    volume: float | None = None
    group_id: int | None = None
