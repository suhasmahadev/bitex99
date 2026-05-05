"""
Surge detector — SPEC2.md Section 14.

Checks Redis manual toggle keys and IST time-based peak hours.
Peak: 12-14 (lunch), 19-22 (dinner), 23-02 (late night).
Weekend bonus on Sat/Sun.
Rain bonus via Redis key.
"""

import logging
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# IST offset: UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))


async def is_surge_active(city: str, redis: aioredis.Redis) -> bool:
    """Check if surge pricing is active for a city."""
    # Manual admin toggle
    manual = await redis.get(f"surge:MANUAL:{city}")
    if manual:
        return True

    now_ist = datetime.now(IST)
    hour = now_ist.hour

    # Peak hours
    if 12 <= hour < 14:       # lunch peak
        return True
    if 19 <= hour < 22:       # dinner peak
        return True
    if hour >= 23 or hour < 2:  # late night
        return True

    return False


async def get_surge_pay(city: str, redis: aioredis.Redis) -> float:
    """Calculate total surge pay amount for current conditions."""
    total = 0.0
    now_ist = datetime.now(IST)
    hour = now_ist.hour

    # Lunch / dinner peak: +₹10
    if 12 <= hour < 14 or 19 <= hour < 22:
        total += 10.0

    # Late night: +₹15
    if hour >= 23 or hour < 2:
        total += 15.0

    # Rain bonus: +₹20
    rain_key = await redis.get(f"surge:RAIN:{city}")
    if rain_key:
        total += 20.0

    # Weekend: +₹5
    today = now_ist.weekday()
    if today >= 5:  # Saturday=5, Sunday=6
        total += 5.0

    return total
