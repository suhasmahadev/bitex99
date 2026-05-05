"""
Pydantic schemas for role selection and onboarding.
"""

from pydantic import BaseModel, Field
from app.models.user import UserRole


class RoleSelectionRequest(BaseModel):
    role: UserRole


# ── Customer Onboarding ───────────────────────────────────────────────────────

class CustomerBasicRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    gender: str = Field(..., max_length=50)


class CustomerAddressRequest(BaseModel):
    address: str = Field(..., min_length=5, max_length=1000)


# ── Delivery Onboarding ───────────────────────────────────────────────────────

class DeliveryBasicRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)


class DeliveryVehicleRequest(BaseModel):
    vehicle_type: str = Field(..., min_length=2, max_length=100)


class DeliveryLicenseRequest(BaseModel):
    license_number: str = Field(..., min_length=5, max_length=100)


# ── Restaurant Onboarding ─────────────────────────────────────────────────────

class RestaurantBasicRequest(BaseModel):
    restaurant_name: str = Field(..., min_length=2, max_length=255)


class RestaurantAddressRequest(BaseModel):
    address: str = Field(..., min_length=5, max_length=1000)


class RestaurantLicenseRequest(BaseModel):
    license_id: str = Field(..., min_length=5, max_length=100)
