"""
Auth router — SPEC.md Section 5 + 6 compliant.
Prefix: /api/v1/auth
Endpoints: send-otp, verify-otp, refresh, logout
"""

import logging
from fastapi import APIRouter, status

from app.dependencies import AuthSvc, CurrentUser, Redis
from app.schemas.auth import (
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SendOTPRequest,
    SendOTPResponse,
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from app.utils import otp as otp_utils

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/send-otp",
    response_model=SendOTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Send OTP to mobile number",
)
async def send_otp(body: SendOTPRequest, redis: Redis) -> SendOTPResponse:
    expires_in = await otp_utils.send_otp(redis, body.phone)
    return SendOTPResponse(message="OTP sent", expires_in=expires_in)


@router.post(
    "/verify-otp",
    response_model=VerifyOTPResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP and issue JWT tokens",
)
async def verify_otp(
    body: VerifyOTPRequest, redis: Redis, auth_svc: AuthSvc,
) -> VerifyOTPResponse:
    if body.register_as_partner and body.register_as_restaurant:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_REGISTRATION", "message": "Cannot register as both partner types"}
        )
    await otp_utils.verify_otp(redis, body.phone, body.otp)
    return await auth_svc.login_with_otp(
        phone=body.phone,
        register_as_partner=body.register_as_partner,
        register_as_restaurant=body.register_as_restaurant,
        referral_code=body.referral_code,
    )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token using refresh token",
)
async def refresh_tokens(body: RefreshTokenRequest, auth_svc: AuthSvc) -> RefreshTokenResponse:
    return await auth_svc.refresh_tokens(body.refresh_token)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout — invalidates refresh token",
)
async def logout(current_user: CurrentUser, auth_svc: AuthSvc) -> LogoutResponse:
    await auth_svc.logout(current_user.id)
    return LogoutResponse()
