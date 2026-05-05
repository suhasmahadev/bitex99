"""
Pydantic schemas for order placement and lifecycle tracking.
Aligned with SPEC.md Section 4 & 6.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.order import OrderStatus, PaymentMethod, PaymentStatus


# ── Requests ──────────────────────────────────────────────────────────────────

class PlaceOrderRequest(BaseModel):
    delivery_address_id: uuid.UUID
    payment_method: PaymentMethod = PaymentMethod.COD
    coupon_code: str | None = Field(None, max_length=50)


class CancelOrderRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class UpdateOrderStatusRequest(BaseModel):
    """Used internally / by webhook to advance order status."""
    status: OrderStatus


# ── Response sub-objects ──────────────────────────────────────────────────────

class OrderItemResponse(BaseModel):
    menu_item_id: uuid.UUID | None
    name: str
    price: float
    quantity: int
    item_total: float

    model_config = {"from_attributes": True}


class OrderRestaurantInfo(BaseModel):
    id: uuid.UUID
    name: str
    image_url: str | None = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    restaurant: OrderRestaurantInfo
    delivery_address: dict[str, Any]
    items: list[OrderItemResponse]
    items_total: float
    delivery_fee: float
    discount_amount: float
    coupon_code: str | None
    total_amount: float
    cancellation_reason: str | None = None
    estimated_delivery_at: datetime | None = None
    created_at: datetime


class OrderListItem(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    payment_status: PaymentStatus
    total_amount: float
    restaurant_name: str | None = None
    item_count: int
    created_at: datetime
