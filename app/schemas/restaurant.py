"""
Pydantic schemas for restaurant discovery, search, and detail.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RestaurantListResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    image_url: str | None
    cuisine_types: list[str]
    city: str
    rating: float
    total_reviews: int
    avg_delivery_time: int | None
    min_order_amount: float
    is_pure_veg: bool
    is_open: bool
    has_offers: bool

    model_config = {"from_attributes": True}


class RestaurantDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    image_url: str | None
    cuisine_types: list[str]
    full_address: str
    city: str
    latitude: float | None
    longitude: float | None
    rating: float
    total_reviews: int
    avg_delivery_time: int | None
    min_order_amount: float
    is_pure_veg: bool
    is_open: bool
    has_offers: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RestaurantSearchParams(BaseModel):
    q: str | None = Field(None, description="Search query for name or cuisine")
    city: str | None = Field(None, description="Filter by city")
    cuisine: str | None = Field(None, description="Filter by cuisine type")
    is_veg_only: bool | None = Field(None, description="Veg-only restaurants")
    is_open: bool | None = Field(None, description="Currently open restaurants")
    sort_by: str = Field("avg_rating", description="Sort by: avg_rating, cost_for_two, avg_delivery_time_min")
    sort_order: str = Field("desc", description="Sort order: asc or desc")
    min_rating: float | None = Field(None, ge=0, le=5, description="Minimum average rating")


class CouponResponse(BaseModel):
    id: uuid.UUID
    code: str
    description: str | None
    discount_type: str
    discount_value: float
    min_order_amount: float
    max_discount: float | None
    is_active: bool

    model_config = {"from_attributes": True}


class ValidateCouponRequest(BaseModel):
    code: str = Field(..., max_length=50)
    restaurant_id: uuid.UUID | None = None
    order_amount: float = Field(..., gt=0)


class CouponDiscountResponse(BaseModel):
    code: str
    discount_type: str
    discount_value: float
    calculated_discount: float
    final_amount: float
