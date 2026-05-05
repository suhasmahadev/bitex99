from fastapi import APIRouter, HTTPException
from app.dependencies import DB, CurrentUser, RestaurantUser, ApprovedRestaurant
from app.schemas.restaurant_partner import (
    RestaurantSetupRequest, OpenToggleRequest, ProfileUpdateRequest, RestaurantTimingRequest
)
from app.services.restaurant_partner_service import RestaurantPartnerService

router = APIRouter(prefix="/api/v1/restaurant/profile", tags=["Restaurant Profile"])

@router.post("/setup")
async def setup_restaurant(
    body: RestaurantSetupRequest,
    current_user: CurrentUser,
    db: DB,
    partner: RestaurantUser
):
    if current_user.restaurant_status not in ["PENDING_DOCS", "DOCS_REJECTED"]:
        raise HTTPException(status_code=403, detail="Cannot setup restaurant in current status")
    
    svc = RestaurantPartnerService(db)
    return await svc.setup_restaurant(current_user.id, body)

@router.get("")
async def get_profile(
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = RestaurantPartnerService(db)
    return await svc.get_profile(current_user.id)

@router.patch("")
async def update_profile(
    body: ProfileUpdateRequest,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = RestaurantPartnerService(db)
    return await svc.update_profile(current_user.id, body.model_dump(exclude_unset=True))

@router.post("/open-toggle")
async def toggle_open(
    body: OpenToggleRequest,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = RestaurantPartnerService(db)
    return await svc.toggle_open_status(current_user.id, body.is_open)

@router.get("/timings")
async def get_timings(
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = RestaurantPartnerService(db)
    return await svc.get_timings(current_user.id)

@router.patch("/timings")
async def update_timings(
    body: list[RestaurantTimingRequest],
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = RestaurantPartnerService(db)
    return await svc.update_timings(current_user.id, [b.model_dump() for b in body])
