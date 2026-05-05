from datetime import datetime
from pydantic import BaseModel
from typing import List

class DocumentStatus(BaseModel):
    doc_type: str
    status: str | None = None
    uploaded_at: datetime | None = None
    rejection_reason: str | None = None

class KYCStatusResponse(BaseModel):
    overall_status: str | None = None
    documents: List[DocumentStatus]
    missing_required: List[str]
    can_submit: bool

class AdminRejectRequest(BaseModel):
    doc_type: str
    reason: str
