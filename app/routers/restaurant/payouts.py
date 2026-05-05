from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.dependencies import ApprovedRestaurant, DB
from app.services.restaurant_payout_service import RestaurantPayoutService

router = APIRouter(prefix="/api/v1/restaurant/payouts", tags=["Restaurant Payouts"])


class PayoutRequest(BaseModel):
    amount: float = Field(gt=0)


@router.get("")
async def payout_history(
    partner: ApprovedRestaurant,
    db: DB,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    return await RestaurantPayoutService().get_payout_history(partner.id, db, page, limit)


@router.get("/pending")
async def pending_payout(partner: ApprovedRestaurant, db: DB):
    return await RestaurantPayoutService().get_pending_payout(partner.id, db)


@router.post("/request")
async def request_payout(body: PayoutRequest, partner: ApprovedRestaurant, db: DB):
    return await RestaurantPayoutService().request_payout(partner.id, body.amount, db)
