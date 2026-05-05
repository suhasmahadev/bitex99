"""
Pydantic schemas for menu browsing.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class MenuItemResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None
    image_url: str | None
    price: float
    discounted_price: float | None
    effective_price: float
    is_veg: bool
    is_available: bool
    preparation_time: int | None
    tags: list[str]

    model_config = {"from_attributes": True}


class MenuCategoryResponse(BaseModel):
    """Menu items grouped by category."""
    category: str
    items: list[MenuItemResponse]
