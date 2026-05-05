"""
Auth routes — strictly thin: validate input, delegate to services, return response.
No business logic here.
"""

import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.api.deps import get_auth_service, get_otp_service, get_current_user
from app.core.config import get_settings
from app.models.user import User
from app.schemas.user import (
    MessageResponse,
    RefreshTokenRequest,
    SendOTPRequest,
    TokenResponse,
    VerifyOTPRequest,
)
from app.schemas.onboarding import RoleSelectionRequest
from app.services.auth_service import AuthService
from app.services.otp_service import OTPService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── OTP ───────────────────────────────────────────────────────────────────────

@router.post(
    "/send-otp",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send OTP to mobile number",
)
async def send_otp(
    body: SendOTPRequest,
    otp_svc: Annotated[OTPService, Depends(get_otp_service)],
) -> MessageResponse:
    try:
        await otp_svc.send_otp(body.phone)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    return MessageResponse(message=f"OTP sent to {body.phone}")


@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify OTP and issue JWT tokens",
)
async def verify_otp(
    body: VerifyOTPRequest,
    otp_svc: Annotated[OTPService, Depends(get_otp_service)],
    auth_svc: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    is_valid = await otp_svc.verify_otp(body.phone, body.otp)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP",
        )
    try:
        tokens = await auth_svc.login_with_otp(body.phone)
    except Exception as exc:
        logger.exception("Error during OTP login: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")
    return tokens


@router.post(
    "/select-role",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Select user role after OTP verification",
)
async def select_role(
    body: RoleSelectionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    auth_svc: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        tokens = await auth_svc.select_role(current_user.id, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Error during role selection: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Role selection failed")
    return tokens


# ── Token refresh ─────────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token using refresh token",
)
async def refresh_tokens(
    body: RefreshTokenRequest,
    auth_svc: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        tokens = await auth_svc.refresh_tokens(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return tokens


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get(
    "/google/login",
    status_code=status.HTTP_302_FOUND,
    summary="Redirect to Google consent screen",
    include_in_schema=True,
)
async def google_login() -> RedirectResponse:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/google/callback",
    response_model=TokenResponse,
    summary="Google OAuth callback",
)
async def google_callback(
    request: Request,
    auth_svc: Annotated[AuthService, Depends(get_auth_service)],
) -> JSONResponse:
    code = request.query_params.get("code")
    error = request.query_params.get("error")

    if error or not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Missing authorization code",
        )

    try:
        tokens = await auth_svc.exchange_google_code(
            code=code,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )
    except Exception as exc:
        logger.exception("Google OAuth callback error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to complete Google login",
        )

    # Return JSON — the frontend picks this up
    return JSONResponse(content=tokens.model_dump())
