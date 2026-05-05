"""
FastAPI dependency functions:
  - Redis client
  - OTP service
  - Auth service
  - Current user extraction
  - Role-based guards
"""

import logging
import uuid
from functools import lru_cache
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.services.otp_service import OTPService
from app.services.onboarding_service import OnboardingService
from app.utils.jwt import verify_access_token

logger = logging.getLogger(__name__)
settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


# ── Redis ─────────────────────────────────────────────────────────────────────

@lru_cache
def _get_redis_pool() -> aioredis.Redis:
    """Singleton Redis connection pool (reused across requests)."""
    return aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=False,
    )


async def get_redis() -> aioredis.Redis:
    return _get_redis_pool()


# ── Service factories ─────────────────────────────────────────────────────────

async def get_otp_service(
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
) -> OTPService:
    return OTPService(redis)


async def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthService:
    return AuthService(db)


async def get_onboarding_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OnboardingService:
    return OnboardingService(db)


# ── Current user ──────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_exception
    try:
        payload = verify_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError) as exc:
        logger.warning("Token validation failed: %s", exc)
        raise credentials_exception from exc

    user = await auth_service.get_user_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


# ── Role guards ───────────────────────────────────────────────────────────────

def require_role(*roles: UserRole):
    """Factory that returns a dependency enforcing one of the given roles."""
    async def _guard(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return _guard


# Convenience role guards
customer_only = require_role(UserRole.customer)
delivery_only = require_role(UserRole.delivery)
restaurant_only = require_role(UserRole.restaurant)
