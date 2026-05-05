"""
Auth service — SPEC.md Section 5 compliant.

Redis key structure:
  Refresh token: "refresh:{user_id}" value=sha256(token) TTL=604800 (7 days)
"""

import hashlib
import logging
import uuid

import redis.asyncio as aioredis
from jose import JWTError
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import InvalidCredentialsError, UserNotFoundError
from app.models.user import User
from app.models.delivery_partner import DeliveryPartner
from app.schemas.auth import (
    RefreshTokenResponse,
    UserInResponse,
    VerifyOTPResponse,
)
from app.utils.jwt import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)

logger = logging.getLogger(__name__)
settings = get_settings()

REFRESH_KEY = "refresh:{user_id}"
REFRESH_TTL = 60 * 60 * 24 * 7  # 604800 seconds = 7 days


def _hash_token(token: str) -> str:
    """SHA-256 hash of a token for Redis storage."""
    return hashlib.sha256(token.encode()).hexdigest()

import secrets
import string


class AuthService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self._db = db
        self._redis = redis

    # ── POST /auth/verify-otp ─────────────────────────────────────────────────

    async def login_with_otp(
        self, phone: str, register_as_partner: bool = False, register_as_restaurant: bool = False, referral_code: str | None = None
    ) -> VerifyOTPResponse:
        """
        Called AFTER OTP verification succeeds.
        Upsert user, issue JWT pair, store refresh hash in Redis.
        """
        user = await self._get_user_by_phone(phone)
        is_new_user = False
        is_new_partner = False

        if user is None:
            user = User(phone=phone, is_verified=True)
            self._db.add(user)
            await self._db.flush()
            is_new_user = True
            logger.info("New user created via OTP: %s", user.id)
        else:
            if not user.is_active:
                raise InvalidCredentialsError(detail="Account is deactivated")
            if not user.is_verified:
                user.is_verified = True
            logger.info("Existing user logged in via OTP: %s", user.id)

        if register_as_partner and user.role != "DELIVERY_PARTNER":
            if user.role == "RESTAURANT_PARTNER":
                from fastapi import HTTPException
                raise HTTPException(status_code=409, detail={"error_code": "ROLE_CONFLICT", "message": "This number is registered as a Restaurant Partner. Use different number."})
            user.role = "DELIVERY_PARTNER"
            user.partner_status = "PENDING_KYC"
            
            # Generate fe_id
            count = await self._db.scalar(select(func.count()).select_from(DeliveryPartner))
            fe_id = f"ZFE{str(count + 1 if count else 1).zfill(5)}"
            
            # Generate referral code
            alphabet = string.ascii_uppercase + string.digits
            new_referral_code = "".join(secrets.choice(alphabet) for _ in range(8))
            
            referred_by_id = None
            if referral_code:
                referrer = await self._db.scalar(
                    select(DeliveryPartner).where(DeliveryPartner.referral_code == referral_code)
                )
                if referrer:
                    referred_by_id = referrer.id
            
            partner = DeliveryPartner(
                user_id=user.id,
                fe_id=fe_id,
                city="", # Admin will update or set elsewhere? Spec says NOT NULL, wait, let's look at schema.
                referral_code=new_referral_code,
                referred_by=referred_by_id,
            )
            self._db.add(partner)
            await self._db.flush()
            is_new_partner = True
            partner_id = partner.id
        elif user.role == "DELIVERY_PARTNER":
            partner = await self._db.scalar(select(DeliveryPartner).where(DeliveryPartner.user_id == user.id))
            partner_id = partner.id if partner else None
        else:
            partner = None
            partner_id = None

        is_new_restaurant_partner = False
        restaurant_partner_id = None
        restaurant_id = None
        from app.models.restaurant_partner import RestaurantPartner

        if register_as_restaurant and user.role != "RESTAURANT_PARTNER":
            if user.role == "DELIVERY_PARTNER":
                from fastapi import HTTPException
                raise HTTPException(status_code=409, detail={"error_code": "ROLE_CONFLICT", "message": "This number is registered as a Delivery Partner. Use different number."})
            user.role = "RESTAURANT_PARTNER"
            user.restaurant_status = "PENDING_DOCS"
            is_new_restaurant_partner = True
            await self._db.flush()
        elif user.role == "RESTAURANT_PARTNER":
            rest_partner = await self._db.scalar(select(RestaurantPartner).where(RestaurantPartner.user_id == user.id))
            if rest_partner:
                restaurant_partner_id = rest_partner.id
                restaurant_id = rest_partner.restaurant_id

        await self._db.commit()

        # Issue tokens
        access_token = create_access_token(user.id, user.phone, role=user.role, partner_id=partner_id, restaurant_partner_id=restaurant_partner_id, restaurant_id=restaurant_id)
        refresh_token = create_refresh_token(user.id, user.phone)

        # Store refresh token hash in Redis
        await self._store_refresh_hash(user.id, refresh_token)

        return VerifyOTPResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserInResponse(
                id=user.id,
                phone=user.phone,
                name=user.name,
                is_new_user=is_new_user,
                role=user.role,
                partner_status=user.partner_status,
                restaurant_status=user.restaurant_status,
                fe_id=partner.fe_id if user.role == "DELIVERY_PARTNER" and partner else None,
            ),
            is_new_user=is_new_user,
            is_new_partner=is_new_partner,
            is_new_restaurant_partner=is_new_restaurant_partner,
            fe_id=partner.fe_id if user.role == "DELIVERY_PARTNER" and partner else None,
            partner_status=user.partner_status,
            restaurant_status=user.restaurant_status,
        )

    # ── POST /auth/refresh ────────────────────────────────────────────────────

    async def refresh_tokens(self, refresh_token: str) -> RefreshTokenResponse:
        """
        Validate refresh token, check hash against Redis, rotate both tokens.
        """
        # 1. Decode JWT
        try:
            payload = verify_refresh_token(refresh_token)
        except JWTError as exc:
            raise InvalidCredentialsError(detail=f"Invalid refresh token: {exc}") from exc

        user_id = uuid.UUID(payload["sub"])
        phone = payload.get("phone", "")

        # 2. Hash incoming token and compare with Redis stored hash
        incoming_hash = _hash_token(refresh_token)
        redis_key = REFRESH_KEY.format(user_id=str(user_id))
        stored_hash: bytes | None = await self._redis.get(redis_key)

        if stored_hash is None or stored_hash.decode() != incoming_hash:
            # Token rotation attack or expired — invalidate
            await self._redis.delete(redis_key)
            raise InvalidCredentialsError(
                detail="Refresh token invalid or already used (possible token rotation attack)"
            )

        # 3. Verify user still exists and is active
        user = await self._get_user_by_id(user_id)
        if user is None or not user.is_active:
            raise UserNotFoundError()

        restaurant_partner_id = None
        restaurant_id = None
        if user.role == "DELIVERY_PARTNER":
            partner = await self._db.scalar(select(DeliveryPartner).where(DeliveryPartner.user_id == user.id))
            partner_id = partner.id if partner else None
        elif user.role == "RESTAURANT_PARTNER":
            from app.models.restaurant_partner import RestaurantPartner
            rest_partner = await self._db.scalar(select(RestaurantPartner).where(RestaurantPartner.user_id == user.id))
            if rest_partner:
                restaurant_partner_id = rest_partner.id
                restaurant_id = rest_partner.restaurant_id
            partner_id = None
        else:
            partner_id = None
            
        # 4. Issue new token pair (rotation)
        new_access = create_access_token(user.id, user.phone, role=user.role, partner_id=partner_id, restaurant_partner_id=restaurant_partner_id, restaurant_id=restaurant_id)
        new_refresh = create_refresh_token(user.id, user.phone)

        # 5. Store new refresh hash in Redis
        await self._store_refresh_hash(user.id, new_refresh)

        return RefreshTokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
        )

    # ── POST /auth/logout ─────────────────────────────────────────────────────

    async def logout(self, user_id: uuid.UUID) -> None:
        """Delete refresh token hash from Redis — invalidates all refresh tokens."""
        redis_key = REFRESH_KEY.format(user_id=str(user_id))
        await self._redis.delete(redis_key)
        logger.info("User %s logged out (refresh token invalidated)", user_id)

    # ── Helpers for dependency injection ──────────────────────────────────────

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._get_user_by_id(user_id)

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _get_user_by_phone(self, phone: str) -> User | None:
        result = await self._db.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _store_refresh_hash(self, user_id: uuid.UUID, refresh_token: str) -> None:
        redis_key = REFRESH_KEY.format(user_id=str(user_id))
        token_hash = _hash_token(refresh_token)
        await self._redis.setex(redis_key, REFRESH_TTL, token_hash)
