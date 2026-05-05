import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict, constr

class RestaurantSetupRequest(BaseModel):
    restaurant_name: str = Field(..., min_length=2, max_length=200)
    business_type: Literal['RESTAURANT', 'CLOUD_KITCHEN', 'BAKERY', 'CAFE', 'FOOD_TRUCK']
    cuisine_types: list[str] = Field(..., min_length=1)
    city: str
    full_address: str
    latitude: float | None = None
    longitude: float | None = None
    phone: str
    owner_name: str
    fssai_number: str = Field(..., pattern=r"^\d{14}$")
    fssai_expiry: date
    gstin: str | None = None
    pan_number: str = Field(..., pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")
    bank_account_number: str
    bank_ifsc: str = Field(..., min_length=11, max_length=11)
    bank_account_name: str
    min_order_amount: float = 0
    avg_delivery_time: int = 45
    delivery_fee: float = 30
    description: str | None = None


class RestaurantPartnerResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    owner_name: str
    business_type: str
    commission_rate: float
    wallet_balance: float
    total_revenue: float
    total_orders: int
    fssai_number: str
    fssai_expiry: date | None
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RestaurantTimingRequest(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    opens_at: str = Field(..., pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    closes_at: str = Field(..., pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    is_closed: bool = False


class OpenToggleRequest(BaseModel):
    is_open: bool

class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    cuisine_types: list[str] | None = None
    phone: str | None = None
    image_url: str | None = None
    cover_image_url: str | None = None
    min_order_amount: float | None = None
    avg_delivery_time: int | None = None
    delivery_fee: float | None = None
    is_pure_veg: bool | None = None
