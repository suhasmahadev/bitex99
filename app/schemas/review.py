"""
Pydantic schemas for Review endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateReviewRequest(BaseModel):
    order_id: uuid.UUID
    food_rating: int = Field(..., ge=1, le=5)
    delivery_rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=2000)


class ReviewResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    restaurant_id: uuid.UUID
    food_rating: int
    delivery_rating: int
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewListItem(BaseModel):
    id: uuid.UUID
    food_rating: int
    delivery_rating: int
    comment: str | None
    created_at: datetime
    user_first_name: str | None = None
