"""
JWT utility — SPEC.md Section 5 compliant.
Payload: { "sub": user_id, "phone": phone, "iat": now, "exp": expiry, "jti": uuid4() }
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def _create_token(
    user_id: uuid.UUID,
    phone: str,
    token_type: str,
    expires_delta: timedelta,
    role: str | None = None,
    partner_id: uuid.UUID | None = None,
    restaurant_partner_id: uuid.UUID | None = None,
    restaurant_id: uuid.UUID | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "phone": phone,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if role is not None:
        payload["role"] = role
    if partner_id is not None:
        payload["partner_id"] = str(partner_id)
    if restaurant_partner_id is not None:
        payload["restaurant_partner_id"] = str(restaurant_partner_id)
    if restaurant_id is not None:
        payload["restaurant_id"] = str(restaurant_id)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(
    user_id: uuid.UUID, 
    phone: str, 
    role: str | None = None, 
    partner_id: uuid.UUID | None = None,
    restaurant_partner_id: uuid.UUID | None = None,
    restaurant_id: uuid.UUID | None = None,
) -> str:
    """Create a short-lived access token (30 min per spec)."""
    return _create_token(
        user_id=user_id,
        phone=phone,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        role=role,
        partner_id=partner_id,
        restaurant_partner_id=restaurant_partner_id,
        restaurant_id=restaurant_id,
    )


def create_refresh_token(user_id: uuid.UUID, phone: str) -> str:
    """Create a long-lived refresh token (7 days per spec)."""
    return _create_token(
        user_id=user_id,
        phone=phone,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises JWTError on failure."""
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )


def verify_access_token(token: str) -> dict[str, Any]:
    """Decode and assert the token is an access token."""
    payload = decode_token(token)
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise JWTError("Token type mismatch: expected access token")
    return payload


def verify_refresh_token(token: str) -> dict[str, Any]:
    """Decode and assert the token is a refresh token."""
    payload = decode_token(token)
    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise JWTError("Token type mismatch: expected refresh token")
    return payload
