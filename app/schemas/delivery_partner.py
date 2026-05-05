from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PartnerProfileUpdate(BaseModel):
    name: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_number: Optional[str] = None
    vehicle_model: Optional[str] = None

class PartnerProfileResponse(BaseModel):
    fe_id: str | None
    name: str | None
    phone: str
    city: str | None
    vehicle_type: str | None
    vehicle_number: str | None
    vehicle_model: str | None
    is_online: bool
    rating: float
    total_ratings: int
    joined_at: datetime
    overall_kyc_status: str | None
