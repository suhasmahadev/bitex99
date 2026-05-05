"""
Custom exception classes and FastAPI exception handlers.
All service-layer errors raise these; routers never build HTTPException directly.
All error codes are returned in SCREAMING_SNAKE_CASE per SPEC.md Section 8.
"""

import logging
import re
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Base ──────────────────────────────────────────────────────────────────────

class AppException(Exception):
    """Base application exception."""
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An unexpected error occurred"

    def __init__(self, detail: str | None = None, **kwargs: Any) -> None:
        self.detail = detail or self.__class__.detail
        self.extra = kwargs
        super().__init__(self.detail)

    @property
    def error_code(self) -> str:
        # Auto-convert class name to SCREAMING_SNAKE_CASE, e.g., EmptyCartError -> EMPTY_CART_ERROR
        name = self.__class__.__name__
        if name.endswith("Error"):
            name = name[:-5]
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


# ── Auth / OTP ────────────────────────────────────────────────────────────────

class InvalidOTPError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Invalid or expired OTP"

    def __init__(self, detail: str | None = None, error_code: str = "INVALID_OTP", **kwargs: Any) -> None:
        super().__init__(detail=detail, **kwargs)
        self._custom_code = error_code

    @property
    def error_code(self) -> str:
        return self._custom_code


class OTPCooldownError(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "OTP already sent. Wait before requesting again."

    def __init__(self, seconds_remaining: int = 0, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.seconds_remaining = seconds_remaining

    @property
    def error_code(self) -> str:
        return "OTP_COOLDOWN"


class OTPRateLimitError(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Too many OTP requests. Please wait before retrying."

    def __init__(self, detail: str | None = None, error_code: str = "TOO_MANY_OTP_ATTEMPTS", **kwargs: Any) -> None:
        super().__init__(detail=detail, **kwargs)
        self._custom_code = error_code
        
    @property
    def error_code(self) -> str:
        return self._custom_code


class InvalidCredentialsError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Could not validate credentials"


class TokenExpiredError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Token has expired"


# ── Authorization ─────────────────────────────────────────────────────────────

class ForbiddenError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Access denied"


# ── Not Found ─────────────────────────────────────────────────────────────────

class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class UserNotFoundError(NotFoundError):
    detail = "User not found"


class RestaurantNotFoundError(NotFoundError):
    detail = "Restaurant not found"


class MenuItemNotFoundError(NotFoundError):
    detail = "Menu item not found"


class OrderNotFoundError(NotFoundError):
    detail = "Order not found"


class AddressNotFoundError(NotFoundError):
    detail = "Address not found"


class CouponNotFoundError(NotFoundError):
    detail = "Coupon not found"


# ── Conflict / Validation ─────────────────────────────────────────────────────

class ConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource conflict"


class CartRestaurantConflictError(ConflictError):
    detail = "Cart contains items from a different restaurant. Clear your cart first."


class InvalidCouponError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Invalid or expired coupon"


class InvalidOrderTransitionError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Invalid order status transition"


class EmptyCartError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Cart is empty"

    @property
    def error_code(self) -> str:
        return "CART_EMPTY"


class ReviewAlreadyExistsError(ConflictError):
    detail = "You have already reviewed this order"


class RestaurantClosedError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Restaurant is currently closed"


# ── Handler registration ─────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers with the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "AppException [%s] %s — %s",
            exc.status_code,
            exc.__class__.__name__,
            exc.detail,
        )
        content: dict[str, Any] = {
            "success": False,
            "message": exc.detail,
            "error_code": exc.error_code,
        }
        # Include seconds_remaining for cooldown errors
        if hasattr(exc, "seconds_remaining"):
            content["seconds_remaining"] = exc.seconds_remaining
        # Include attempts_remaining for OTP verify failures
        if hasattr(exc, "extra") and "attempts_remaining" in exc.extra:
            content["attempts_remaining"] = exc.extra["attempts_remaining"]
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Internal server error",
                "error_code": "INTERNAL_ERROR",
            },
        )
