"""
OTP generation, storage, verification — SPEC.md Section 5 compliant.

Redis key structure (DO NOT DEVIATE):
  OTP storage:     "otp:{phone}"           value="{otp}:{attempts}"  TTL=300
  Resend cooldown: "otp:cooldown:{phone}"  value="1"                 TTL=60
"""

import logging
import secrets

import redis.asyncio as aioredis

from app.config import get_settings
from app.exceptions import InvalidOTPError, OTPCooldownError, OTPRateLimitError

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis key templates — exactly per spec
OTP_KEY = "otp:{phone}"
COOLDOWN_KEY = "otp:cooldown:{phone}"


def generate_otp() -> str:
    """Generate 6-digit OTP. secrets.randbelow(900000)+100000 guarantees no leading zeros."""
    return str(secrets.randbelow(900000) + 100000)


async def send_otp(redis: aioredis.Redis, phone: str) -> int:
    """
    Check cooldown → generate → store → set cooldown → log.
    Returns expires_in (seconds).

    Raises OTPCooldownError with seconds_remaining if cooldown active.
    """
    # 1. Check cooldown — if exists, reject with seconds_remaining
    cooldown_key = COOLDOWN_KEY.format(phone=phone)
    ttl = await redis.ttl(cooldown_key)
    if ttl > 0:
        raise OTPCooldownError(seconds_remaining=ttl)

    # 2. Generate OTP
    otp = generate_otp()

    # 3. Store as "{otp}:0" (0 = zero attempts so far) with 300s TTL
    otp_key = OTP_KEY.format(phone=phone)
    await redis.setex(otp_key, settings.OTP_TTL_SECONDS, f"{otp}:0")

    # 4. Set cooldown: 60 seconds before next send allowed
    await redis.setex(cooldown_key, 60, "1")

    # 5. Log to console (dev mode); in prod, call SMS gateway
    logger.info("OTP for %s -> %s (expires in %ds)", phone, otp, settings.OTP_TTL_SECONDS)

    return settings.OTP_TTL_SECONDS


async def verify_otp(redis: aioredis.Redis, phone: str, otp: str) -> bool:
    """
    Verify OTP from Redis. Single-use: deletes on success.
    Enforces max-attempts lockout (3 attempts).

    Returns True on success.
    Raises InvalidOTPError on wrong code (with attempts_remaining).
    Raises OTPRateLimitError after 3 failures (key deleted = must request new OTP).
    """
    otp_key = OTP_KEY.format(phone=phone)

    # 1. Fetch key — if missing, OTP expired or never sent
    stored: bytes | None = await redis.get(otp_key)
    if stored is None:
        raise InvalidOTPError(
            detail="OTP expired or not found",
            error_code="OTP_EXPIRED",
        )

    # 2. Parse "{stored_otp}:{attempts}"
    parts = stored.decode().split(":")
    if len(parts) != 2:
        # Corrupted key — delete and reject
        await redis.delete(otp_key)
        raise InvalidOTPError(detail="OTP expired or not found", error_code="OTP_EXPIRED")

    stored_otp, attempts_str = parts
    attempts = int(attempts_str)

    # 3. If attempts >= 3: delete key, return 429
    if attempts >= settings.OTP_MAX_ATTEMPTS:
        await redis.delete(otp_key)
        raise OTPRateLimitError(
            detail="Too many attempts. Request new OTP",
            error_code="TOO_MANY_OTP_ATTEMPTS",
        )

    # 4. If OTP doesn't match: increment attempts in-place (keep same TTL)
    if otp != stored_otp:
        new_attempts = attempts + 1
        # Get remaining TTL so we preserve it
        remaining_ttl = await redis.ttl(otp_key)
        if remaining_ttl <= 0:
            remaining_ttl = settings.OTP_TTL_SECONDS

        if new_attempts >= settings.OTP_MAX_ATTEMPTS:
            # This was the 3rd wrong attempt — delete and block
            await redis.delete(otp_key)
            raise OTPRateLimitError(
                detail="Too many attempts. Request new OTP",
                error_code="TOO_MANY_OTP_ATTEMPTS",
            )

        # Update with incremented attempt counter, same TTL
        await redis.setex(otp_key, remaining_ttl, f"{stored_otp}:{new_attempts}")
        raise InvalidOTPError(
            detail="Invalid OTP",
            error_code="INVALID_OTP",
            attempts_remaining=settings.OTP_MAX_ATTEMPTS - new_attempts,
        )

    # 5. SUCCESS — delete key to prevent replay
    await redis.delete(otp_key)
    return True
