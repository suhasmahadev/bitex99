"""
OTP service: generate, store in Redis, and verify OTPs.
Includes Redis-backed rate limiting.
"""

import logging

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.security import generate_otp

logger = logging.getLogger(__name__)
settings = get_settings()

OTP_KEY_PREFIX = "otp:"
RATE_LIMIT_KEY_PREFIX = "otp_rate:"


class OTPService:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    # ── Public API ────────────────────────────────────────────────────────────

    async def send_otp(self, phone: str) -> None:
        """
        Rate-check, generate OTP, store in Redis, and log to console.
        Raises ValueError on rate limit or Redis failure.
        """
        await self._check_rate_limit(phone)
        otp = generate_otp()
        await self._store_otp(phone, otp)
        # In production replace this with an SMS gateway call
        logger.info("📲  OTP for %s → %s", phone, otp)
        await self._increment_rate_counter(phone)

    async def verify_otp(self, phone: str, otp: str) -> bool:
        """
        Verify OTP from Redis.
        Deletes the OTP on successful verification (one-time use).
        Returns True on match, False otherwise.
        """
        key = self._otp_key(phone)
        stored: bytes | None = await self._redis.get(key)
        if stored is None:
            logger.warning("OTP expired or not found for %s", phone)
            return False
        if stored.decode() != otp:
            logger.warning("Invalid OTP attempt for %s", phone)
            return False
        # Consume the OTP (single-use)
        await self._redis.delete(key)
        return True

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _store_otp(self, phone: str, otp: str) -> None:
        key = self._otp_key(phone)
        await self._redis.setex(key, settings.OTP_TTL_SECONDS, otp)

    async def _check_rate_limit(self, phone: str) -> None:
        key = self._rate_key(phone)
        count_raw: bytes | None = await self._redis.get(key)
        count = int(count_raw) if count_raw else 0
        if count >= settings.OTP_RATE_LIMIT_MAX:
            raise ValueError(
                f"Too many OTP requests. Try again after {settings.OTP_RATE_LIMIT_WINDOW // 60} minutes."
            )

    async def _increment_rate_counter(self, phone: str) -> None:
        key = self._rate_key(phone)
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, settings.OTP_RATE_LIMIT_WINDOW)
        await pipe.execute()

    @staticmethod
    def _otp_key(phone: str) -> str:
        return f"{OTP_KEY_PREFIX}{phone}"

    @staticmethod
    def _rate_key(phone: str) -> str:
        return f"{RATE_LIMIT_KEY_PREFIX}{phone}"
