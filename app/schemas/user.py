"""
Pydantic schemas for user profile.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    phone: str
    name: str | None
    email: str | None
    avatar_url: str | None = None
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(None, max_length=255)
    email: EmailStr | None = None
    profile_picture: str | None = None
