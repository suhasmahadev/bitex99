"""
Coupon schemas — validate endpoint request/response.
"""

from pydantic import BaseModel, Field


class ValidateCouponRequest(BaseModel):
    code: str = Field(..., max_length=50)
    order_amount: float = Field(..., gt=0)


class ValidateCouponData(BaseModel):
    is_valid: bool
    coupon_code: str
    discount_type: str
    discount_amount: float
    final_amount: float
    message: str


class ValidateCouponResponse(BaseModel):
    success: bool = True
    data: ValidateCouponData
