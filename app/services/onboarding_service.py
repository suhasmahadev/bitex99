"""
Onboarding service: handle step-by-step onboarding for different roles.
"""

import uuid
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.profile import CustomerProfile, DeliveryProfile, RestaurantProfile

logger = logging.getLogger(__name__)


class OnboardingService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _get_user(self, user_id: uuid.UUID) -> User:
        user = await self._db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        return user

    # ── Customer Onboarding ───────────────────────────────────────────────────

    async def _get_or_create_customer(self, user_id: uuid.UUID) -> CustomerProfile:
        profile = await self._db.get(CustomerProfile, user_id)
        if not profile:
            profile = CustomerProfile(user_id=user_id)
            self._db.add(profile)
        return profile

    async def onboard_customer_basic(self, user_id: uuid.UUID, name: str, gender: str) -> None:
        profile = await self._get_or_create_customer(user_id)
        profile.name = name
        profile.gender = gender
        await self._db.commit()

    async def onboard_customer_address(self, user_id: uuid.UUID, address: str) -> None:
        profile = await self._get_or_create_customer(user_id)
        profile.address = address
        user = await self._get_user(user_id)
        user.is_onboarded = True
        await self._db.commit()

    # ── Delivery Onboarding ───────────────────────────────────────────────────

    async def _get_or_create_delivery(self, user_id: uuid.UUID) -> DeliveryProfile:
        profile = await self._db.get(DeliveryProfile, user_id)
        if not profile:
            profile = DeliveryProfile(user_id=user_id)
            self._db.add(profile)
        return profile

    async def onboard_delivery_basic(self, user_id: uuid.UUID, name: str) -> None:
        profile = await self._get_or_create_delivery(user_id)
        profile.name = name
        await self._db.commit()

    async def onboard_delivery_vehicle(self, user_id: uuid.UUID, vehicle_type: str) -> None:
        profile = await self._get_or_create_delivery(user_id)
        profile.vehicle_type = vehicle_type
        await self._db.commit()

    async def onboard_delivery_license(self, user_id: uuid.UUID, license_number: str) -> None:
        profile = await self._get_or_create_delivery(user_id)
        profile.license_number = license_number
        user = await self._get_user(user_id)
        user.is_onboarded = True
        await self._db.commit()

    # ── Restaurant Onboarding ─────────────────────────────────────────────────

    async def _get_or_create_restaurant(self, user_id: uuid.UUID) -> RestaurantProfile:
        profile = await self._db.get(RestaurantProfile, user_id)
        if not profile:
            profile = RestaurantProfile(user_id=user_id)
            self._db.add(profile)
        return profile

    async def onboard_restaurant_basic(self, user_id: uuid.UUID, restaurant_name: str) -> None:
        profile = await self._get_or_create_restaurant(user_id)
        profile.restaurant_name = restaurant_name
        await self._db.commit()

    async def onboard_restaurant_address(self, user_id: uuid.UUID, address: str) -> None:
        profile = await self._get_or_create_restaurant(user_id)
        profile.address = address
        await self._db.commit()

    async def onboard_restaurant_license(self, user_id: uuid.UUID, license_id: str) -> None:
        profile = await self._get_or_create_restaurant(user_id)
        profile.license_id = license_id
        user = await self._get_user(user_id)
        user.is_onboarded = True
        await self._db.commit()
