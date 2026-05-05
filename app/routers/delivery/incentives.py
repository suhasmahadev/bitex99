from fastapi import APIRouter
from app.dependencies import ApprovedPartner, DB
from app.services import incentive_service

router = APIRouter(prefix="/api/v1/partner/incentives", tags=["Partner Incentives"])

@router.get("/active")
async def get_active_incentives(
    partner: ApprovedPartner,
    db: DB
):
    results = await incentive_service.get_active_incentives_with_progress(partner.id, db)
    return {"incentives": results}
