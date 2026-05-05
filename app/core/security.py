"""
Security utilities: OTP generation and cryptographic helpers.
"""

import secrets
import string
import logging

logger = logging.getLogger(__name__)


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically secure numeric OTP."""
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))
