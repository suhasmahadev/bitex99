from typing import Any
from fastapi import APIRouter, Depends, Form, UploadFile, File
from app.dependencies import CurrentPartner, DB
from app.schemas.kyc import KYCStatusResponse
from app.services.kyc_service import KYCService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/partner/kyc", tags=["Partner KYC"])

def get_kyc_service(db: DB) -> KYCService:
    return KYCService(db)

@router.get("/status", response_model=KYCStatusResponse)
async def get_kyc_status(
    current_partner: CurrentPartner,
    kyc_svc: KYCService = Depends(get_kyc_service)
) -> KYCStatusResponse:
    return await kyc_svc.get_kyc_status(current_partner.id)

@router.post("/upload", response_model=KYCStatusResponse)
async def upload_kyc_document(
    current_partner: CurrentPartner,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    kyc_svc: KYCService = Depends(get_kyc_service)
) -> KYCStatusResponse:
    return await kyc_svc.upload_document(current_partner.id, doc_type, file)

@router.post("/submit")
async def submit_kyc(
    current_partner: CurrentPartner,
    kyc_svc: KYCService = Depends(get_kyc_service)
) -> dict[str, str]:
    return await kyc_svc.submit_kyc(current_partner.id)
