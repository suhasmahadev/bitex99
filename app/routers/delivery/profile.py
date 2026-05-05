from fastapi import APIRouter, Depends
from app.dependencies import CurrentPartner, ApprovedPartner, DB
from app.schemas.delivery_partner import PartnerProfileUpdate, PartnerProfileResponse
from app.services.delivery_partner_service import DeliveryPartnerService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/partner/profile", tags=["Partner Profile"])

def get_partner_service(db: DB) -> DeliveryPartnerService:
    return DeliveryPartnerService(db)

@router.get("", response_model=PartnerProfileResponse)
async def get_profile(
    current_partner: CurrentPartner,
    svc: DeliveryPartnerService = Depends(get_partner_service)
) -> PartnerProfileResponse:
    return await svc.get_profile(current_partner.id)

@router.patch("", response_model=PartnerProfileResponse)
async def update_profile(
    data: PartnerProfileUpdate,
    approved_partner: ApprovedPartner,
    svc: DeliveryPartnerService = Depends(get_partner_service)
) -> PartnerProfileResponse:
    return await svc.update_profile(approved_partner.id, data)

@router.get("/stats")
async def get_stats(
    approved_partner: ApprovedPartner,
    svc: DeliveryPartnerService = Depends(get_partner_service)
) -> dict:
    return await svc.get_stats(approved_partner.id)
