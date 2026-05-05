"""
Pydantic schemas for address CRUD.
Aligned with SPEC.md Section 4 and Address model.
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.models.address import AddressLabel


class CreateAddressRequest(BaseModel):
    label: AddressLabel = Field(default=AddressLabel.HOME)
    full_address: str = Field(..., max_length=1000)
    landmark: str | None = Field(None, max_length=200)
    latitude: float | None = None
    longitude: float | None = None
    is_default: bool = False

    @field_validator("label", mode="before")
    @classmethod
    def convert_label(cls, v):
        if isinstance(v, str):
            v = v.upper()
        return v

class UpdateAddressRequest(BaseModel):
    label: AddressLabel | None = None
    full_address: str | None = Field(None, max_length=1000)
    landmark: str | None = Field(None, max_length=200)
    latitude: float | None = None
    longitude: float | None = None
    is_default: bool | None = None

    @field_validator("label", mode="before")
    @classmethod
    def convert_update_label(cls, v):
        if isinstance(v, str):
            v = v.upper()
        return v


class AddressResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    label: AddressLabel
    full_address: str
    landmark: str | None
    latitude: float | None
    longitude: float | None
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}
