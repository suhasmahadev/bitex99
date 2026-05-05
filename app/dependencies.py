"""
FastAPI dependency injection: DB session, Redis, service factories, current user, rate limiting.
"""
import logging
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import InvalidCredentialsError
from sqlalchemy import select
from app.models.user import User
from app.models.delivery_partner import DeliveryPartner
from app.models.restaurant_partner import RestaurantPartner
from app.redis_client import get_redis
from app.services.address_service import AddressService
from app.services.auth_service import AuthService
from app.services.cart_service import CartService
from app.services.menu_service import MenuService
from app.services.order_service import OrderService
from app.services.restaurant_service import RestaurantService
from app.services.review_service import ReviewService
from app.services.user_service import UserService
from app.utils.jwt import verify_access_token
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)

# ── Redis dependency ──────────────────────────────────────────────────────────

async def redis_dep() -> aioredis.Redis:
    return get_redis()


# ── Service factories ─────────────────────────────────────────────────────────

async def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[aioredis.Redis, Depends(redis_dep)],
) -> AuthService:
    return AuthService(db, redis)

async def get_user_service(db: Annotated[AsyncSession, Depends(get_db)]) -> UserService:
    return UserService(db)

async def get_address_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AddressService:
    return AddressService(db)

async def get_restaurant_service(db: Annotated[AsyncSession, Depends(get_db)]) -> RestaurantService:
    return RestaurantService(db)

async def get_menu_service(db: Annotated[AsyncSession, Depends(get_db)]) -> MenuService:
    return MenuService(db)

async def get_cart_service(db: Annotated[AsyncSession, Depends(get_db)]) -> CartService:
    return CartService(db)

async def get_order_service(db: Annotated[AsyncSession, Depends(get_db)]) -> OrderService:
    return OrderService(db)

async def get_review_service(db: Annotated[AsyncSession, Depends(get_db)]) -> ReviewService:
    return ReviewService(db)


# ── Current user ──────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    auth_svc: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise exc
    try:
        payload = verify_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError) as e:
        logger.warning("Token validation failed: %s", e)
        raise exc from e

    user = await auth_svc.get_user_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def require_partner_jwt(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeliveryPartner:
    if current_user.role != "DELIVERY_PARTNER":
        raise HTTPException(status_code=403, detail="Delivery partner role required")
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.user_id == current_user.id))
    if not partner:
        raise HTTPException(status_code=403, detail="Delivery partner profile not found")
    return partner


async def require_approved_partner(
    current_user: User = Depends(get_current_user),
    partner: DeliveryPartner = Depends(require_partner_jwt)
) -> DeliveryPartner:
    if current_user.partner_status != "KYC_APPROVED":
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "KYC_NOT_APPROVED",
                "message": f"Your account is under verification. Status: {current_user.partner_status}",
                "partner_status": current_user.partner_status
            }
        )
    return partner


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


async def require_restaurant_jwt(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RestaurantPartner | None:
    if current_user.role != 'RESTAURANT_PARTNER':
        raise HTTPException(status_code=403, detail={"error_code": "NOT_RESTAURANT_PARTNER"})
    partner = await db.scalar(select(RestaurantPartner).where(RestaurantPartner.user_id == current_user.id))
    return partner


async def require_restaurant_partner(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RestaurantPartner:
    if current_user.role != 'RESTAURANT_PARTNER':
        raise HTTPException(status_code=403, detail={"error_code": "NOT_RESTAURANT_PARTNER"})
    if current_user.restaurant_status != 'DOCS_APPROVED':
        raise HTTPException(status_code=403, detail={
            "error_code": "RESTAURANT_NOT_APPROVED",
            "message": f"Your restaurant is under verification. Status: {current_user.restaurant_status}",
            "restaurant_status": current_user.restaurant_status
        })
    partner = await db.scalar(select(RestaurantPartner).where(RestaurantPartner.user_id == current_user.id))
    if not partner:
        raise HTTPException(status_code=404, detail={"error_code": "RESTAURANT_NOT_FOUND"})
    return partner

# ── Type aliases (for clean router signatures) ────────────────────────────────

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentPartner = Annotated[DeliveryPartner, Depends(require_partner_jwt)]
ApprovedPartner = Annotated[DeliveryPartner, Depends(require_approved_partner)]
AdminUser = Annotated[User, Depends(require_admin)]
RestaurantUser = Annotated[RestaurantPartner | None, Depends(require_restaurant_jwt)]
ApprovedRestaurant = Annotated[RestaurantPartner, Depends(require_restaurant_partner)]
DB = Annotated[AsyncSession, Depends(get_db)]
Redis = Annotated[aioredis.Redis, Depends(redis_dep)]
AuthSvc = Annotated[AuthService, Depends(get_auth_service)]
UserSvc = Annotated[UserService, Depends(get_user_service)]
AddrSvc = Annotated[AddressService, Depends(get_address_service)]
RestSvc = Annotated[RestaurantService, Depends(get_restaurant_service)]
MenuSvc = Annotated[MenuService, Depends(get_menu_service)]
CartSvc = Annotated[CartService, Depends(get_cart_service)]
OrdSvc = Annotated[OrderService, Depends(get_order_service)]
RevSvc = Annotated[ReviewService, Depends(get_review_service)]
