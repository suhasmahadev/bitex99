"""
Coupons router — validate coupon without placing an order.
Reuses the coupon validation logic from order_service.
Prefix: /api/v1/coupons
"""

from datetime import UTC, datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.dependencies import CurrentUser, DB
from app.models.coupon import Coupon, DiscountType
from app.schemas.coupon import ValidateCouponData, ValidateCouponRequest, ValidateCouponResponse

router = APIRouter(prefix="/api/v1/coupons", tags=["Coupons"])


@router.post(
    "/validate",
    response_model=ValidateCouponResponse,
    summary="Validate a coupon code against an order amount",
)
async def validate_coupon(
    body: ValidateCouponRequest,
    current_user: CurrentUser,
    db: DB,
) -> ValidateCouponResponse | JSONResponse:
    code = body.code.strip().upper()
    order_amount = body.order_amount

    res = await db.execute(select(Coupon).where(Coupon.code == code))
    coupon = res.scalar_one_or_none()

    # Not found
    if coupon is None:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error_code": "COUPON_INVALID", "message": "Coupon not found"},
        )

    # Not active
    if not coupon.is_active:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error_code": "COUPON_INVALID", "message": "Coupon is no longer active"},
        )

    # Date validity
    now = datetime.now(UTC).replace(tzinfo=None)
    if coupon.valid_from and coupon.valid_from.replace(tzinfo=None) > now:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error_code": "COUPON_EXPIRED", "message": "Coupon is not yet valid"},
        )
    if coupon.valid_until and coupon.valid_until.replace(tzinfo=None) < now:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error_code": "COUPON_EXPIRED", "message": "Coupon has expired"},
        )

    # Usage limit
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error_code": "COUPON_INVALID", "message": "Coupon usage limit reached"},
        )

    # Min order
    if order_amount < float(coupon.min_order_amount):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error_code": "COUPON_MIN_ORDER",
                "message": f"Minimum order amount is ₹{float(coupon.min_order_amount):.0f}",
            },
        )

    # Compute discount
    if coupon.discount_type == DiscountType.PERCENT:
        disc = order_amount * float(coupon.discount_value) / 100
        if coupon.max_discount is not None:
            disc = min(disc, float(coupon.max_discount))
    else:  # FLAT
        disc = float(coupon.discount_value)

    disc = round(min(disc, order_amount), 2)
    final = round(order_amount - disc, 2)

    if coupon.discount_type == DiscountType.FLAT:
        msg = f"You save \u20b9{disc:.0f} with this coupon"
    else:
        pct = float(coupon.discount_value)
        msg = f"You save {pct:.0f}% (₹{disc:.0f}) with this coupon"

    return ValidateCouponResponse(
        success=True,
        data=ValidateCouponData(
            is_valid=True,
            coupon_code=coupon.code,
            discount_type=coupon.discount_type.value,
            discount_amount=disc,
            final_amount=final,
            message=msg,
        ),
    )
