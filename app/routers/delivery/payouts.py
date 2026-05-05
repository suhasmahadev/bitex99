from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.dependencies import ApprovedPartner, DB
from app.services import payout_service

router = APIRouter(prefix="/api/v1/partner/payouts", tags=["Partner Payouts"])

class PayoutRequest(BaseModel):
    amount: float

@router.get("/pending")
async def get_pending_payout(
    partner: ApprovedPartner,
    db: DB
):
    return await payout_service.get_pending_payout(partner.id, db)

@router.post("/request")
async def request_payout(
    req: PayoutRequest,
    partner: ApprovedPartner,
    db: DB
):
    res = await payout_service.request_payout(partner.id, req.amount, db)
    if "error" in res:
        raise HTTPException(status_code=res.get("status_code", 400), detail=res["error"])
    return res
