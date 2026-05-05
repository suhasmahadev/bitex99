"""
Onboarding routes: step-by-step profile creation based on user role.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, status

from app.api.deps import (
    get_current_user,
    get_onboarding_service,
    customer_only,
    delivery_only,
    restaurant_only,
)
from app.models.user import User
from app.schemas.user import MessageResponse
from app.schemas.onboarding import (
    CustomerBasicRequest,
    CustomerAddressRequest,
    DeliveryBasicRequest,
    DeliveryVehicleRequest,
    DeliveryLicenseRequest,
    RestaurantBasicRequest,
    RestaurantAddressRequest,
    RestaurantLicenseRequest,
)
from app.services.onboarding_service import OnboardingService

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


# ── Customer ──────────────────────────────────────────────────────────────────

@router.post("/customer/basic", response_model=MessageResponse)
async def customer_basic(
    body: CustomerBasicRequest,
    current_user: Annotated[User, Depends(customer_only)],
    onboarding_svc: Annotated[OnboardingService, Depends(get_onboarding_service)],
):
    await onboarding_svc.onboard_customer_basic(current_user.id, body.name, body.gender)
    return MessageResponse(message="Basic profile updated")


@router.post("/customer/address", response_model=MessageResponse)
async def customer_address(
    body: CustomerAddressRequest,
    current_user: Annotated[User, Depends(customer_only)],
    onboarding_svc: Annotated[OnboardingService, Depends(get_onboarding_service)],
):
    await onboarding_svc.onboard_customer_address(current_user.id, body.address)
    return MessageResponse(message="Address updated and onboarding completed")


# ── Delivery ──────────────────────────────────────────────────────────────────

@router.post("/delivery/basic", response_model=MessageResponse)
async def delivery_basic(
    body: DeliveryBasicRequest,
    current_user: Annotated[User, Depends(delivery_only)],
    onboarding_svc: Annotated[OnboardingService, Depends(get_onboarding_service)],
):
    await onboarding_svc.onboard_delivery_basic(current_user.id, body.name)
    return MessageResponse(message="Basic profile updated")


@router.post("/delivery/vehicle", response_model=MessageResponse)
async def delivery_vehicle(
    body: DeliveryVehicleRequest,
    current_user: Annotated[User, Depends(delivery_only)],
    onboarding_svc: Annotated[OnboardingService, Depends(get_onboarding_service)],
):
    await onboarding_svc.onboard_delivery_vehicle(current_user.id, body.vehicle_type)
    return MessageResponse(message="Vehicle information updated")


@router.post("/delivery/license", response_model=MessageResponse)
async def delivery_license(
    body: DeliveryLicenseRequest,
    current_user: Annotated[User, Depends(delivery_only)],
    onboarding_svc: Annotated[OnboardingService, Depends(get_onboarding_service)],
):
    await onboarding_svc.onboard_delivery_license(current_user.id, body.license_number)
    return MessageResponse(message="License information updated and onboarding completed")


# ── Restaurant ────────────────────────────────────────────────────────────────

@router.post("/restaurant/basic", response_model=MessageResponse)
async def restaurant_basic(
    body: RestaurantBasicRequest,
    current_user: Annotated[User, Depends(restaurant_only)],
    onboarding_svc: Annotated[OnboardingService, Depends(get_onboarding_service)],
):
    await onboarding_svc.onboard_restaurant_basic(current_user.id, body.restaurant_name)
    return MessageResponse(message="Restaurant basic profile updated")


@router.post("/restaurant/address", response_model=MessageResponse)
async def restaurant_address(
    body: RestaurantAddressRequest,
    current_user: Annotated[User, Depends(restaurant_only)],
    onboarding_svc: Annotated[OnboardingService, Depends(get_onboarding_service)],
):
    await onboarding_svc.onboard_restaurant_address(current_user.id, body.address)
    return MessageResponse(message="Restaurant address updated")


@router.post("/restaurant/license", response_model=MessageResponse)
async def restaurant_license(
    body: RestaurantLicenseRequest,
    current_user: Annotated[User, Depends(restaurant_only)],
    onboarding_svc: Annotated[OnboardingService, Depends(get_onboarding_service)],
):
    await onboarding_svc.onboard_restaurant_license(current_user.id, body.license_id)
    return MessageResponse(message="Restaurant license updated and onboarding completed")
