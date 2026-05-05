"""
Pydantic schemas for cart management — aligned with SPEC.md Section 6.
Response shapes match the user's exact specification.
"""

import uuid

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────────────

class AddToCartRequest(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=20)


class UpdateQuantityRequest(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(..., ge=0, le=20)  # 0 = remove


class RemoveFromCartRequest(BaseModel):
    menu_item_id: uuid.UUID


# ── Response sub-objects ──────────────────────────────────────────────────────

class CartRestaurantInfo(BaseModel):
    id: uuid.UUID
    name: str
    is_open: bool
    delivery_fee: float

    model_config = {"from_attributes": True}


class CartItemResponse(BaseModel):
    menu_item_id: uuid.UUID
    name: str
    quantity: int
    price: float
    discounted_price: float | None
    effective_price: float
    item_total: float


class CartData(BaseModel):
    restaurant: CartRestaurantInfo | None
    items: list[CartItemResponse]
    items_total: float
    cart_subtotal: float
    delivery_fee: float
    grand_total: float
    item_count: int


class CartResponse(BaseModel):
    success: bool = True
    data: CartData


# ── Conflict response ────────────────────────────────────────────────────────

class RestaurantBrief(BaseModel):
    id: str
    name: str


class CartConflictData(BaseModel):
    existing_restaurant: RestaurantBrief
    new_restaurant: RestaurantBrief


class CartConflictResponse(BaseModel):
    success: bool = False
    error_code: str = "CART_CONFLICT"
    message: str
    data: CartConflictData
