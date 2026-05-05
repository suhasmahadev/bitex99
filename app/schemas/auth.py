"""
Pydantic schemas for authentication — SPEC.md Section 5 compliant.
Phone regex: ^\+[1-9]\d{9,14}$  (E.164, minimum 10 digits after +)
"""

import re
import uuid

from pydantic import BaseModel, Field, field_validator

_E164_PATTERN = re.compile(r"^\+[1-9]\d{9,14}$")


def _validate_e164(v: str) -> str:
    if not _E164_PATTERN.match(v):
        raise ValueError("Phone must be in E.164 format, e.g. +919876543210")
    return v


class SendOTPRequest(BaseModel):
    phone: str = Field(..., examples=["+919876543210"])

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_e164(v)


class SendOTPResponse(BaseModel):
    message: str = "OTP sent"
    expires_in: int = 300


class VerifyOTPRequest(BaseModel):
    phone: str = Field(..., examples=["+919876543210"])
    otp: str = Field(..., min_length=6, max_length=6, examples=["123456"])
    register_as_partner: bool = False
    register_as_restaurant: bool = False
    referral_code: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return _validate_e164(v)

    @field_validator("otp")
    @classmethod
    def otp_digits_only(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("OTP must contain digits only")
        return v


class UserInResponse(BaseModel):
    """Nested user object inside verify-otp response."""
    id: uuid.UUID
    phone: str
    name: str | None = None
    is_new_user: bool = False
    role: str
    partner_status: str | None = None
    restaurant_status: str | None = None
    fe_id: str | None = None

    model_config = {"from_attributes": True}


class VerifyOTPResponse(BaseModel):
    """Exact response shape per SPEC Section 5."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserInResponse
    is_new_user: bool = False
    is_new_partner: bool = False
    is_new_restaurant_partner: bool = False
    fe_id: str | None = None
    partner_status: str | None = None
    restaurant_status: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"


class MessageResponse(BaseModel):
    message: str
