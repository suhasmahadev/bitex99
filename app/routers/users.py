"""
Users router — profile get/update for authenticated customer.
"""
from fastapi import APIRouter, status
from app.dependencies import CurrentUser, UserSvc
from app.schemas.user import UpdateProfileRequest, UserProfileResponse

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me", response_model=UserProfileResponse, summary="Get my profile")
async def get_profile(current_user: CurrentUser, user_svc: UserSvc) -> UserProfileResponse:
    return await user_svc.get_profile(current_user.id)


@router.patch("/me", response_model=UserProfileResponse, summary="Update my profile")
async def update_profile(
    body: UpdateProfileRequest, current_user: CurrentUser, user_svc: UserSvc,
) -> UserProfileResponse:
    return await user_svc.update_profile(current_user.id, body)
