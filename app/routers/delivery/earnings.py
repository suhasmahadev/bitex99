from fastapi import APIRouter
from app.dependencies import ApprovedPartner, DB
from app.services import earnings_service

router = APIRouter(prefix="/api/v1/partner/earnings", tags=["Partner Earnings"])

@router.get("/today")
async def get_today_earnings(
    partner: ApprovedPartner,
    db: DB
):
    return await earnings_service.get_today_earnings(partner.id, db)

@router.get("/weekly")
async def get_weekly_earnings(
    partner: ApprovedPartner,
    db: DB
):
    return await earnings_service.get_weekly_earnings(partner.id, db)
