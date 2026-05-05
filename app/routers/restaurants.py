"""
Restaurants router — discovery, search, detail, coupons.
Public endpoints (no auth required for browsing).
"""
import uuid
from fastapi import APIRouter, Depends, Query
from app.dependencies import RestSvc
from app.schemas.restaurant import (
    CouponDiscountResponse, CouponResponse,
    RestaurantDetailResponse, RestaurantSearchParams,
    ValidateCouponRequest,
)
from app.utils.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/restaurants", tags=["Restaurants"])


@router.get("", response_model=PaginatedResponse, summary="List & search restaurants")
async def list_restaurants(
    rest_svc: RestSvc,
    q: str | None = Query(None),
    city: str | None = Query(None),
    cuisine: str | None = Query(None),
    is_veg_only: bool | None = Query(None),
    is_open: bool | None = Query(None),
    sort_by: str = Query("avg_rating"),
    sort_order: str = Query("desc"),
    min_rating: float | None = Query(None, ge=0, le=5),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse:
    params = RestaurantSearchParams(
        q=q, city=city, cuisine=cuisine, is_veg_only=is_veg_only,
        is_open=is_open, sort_by=sort_by, sort_order=sort_order, min_rating=min_rating,
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    return await rest_svc.list_restaurants(params, pagination)


@router.get("/{restaurant_id}", response_model=RestaurantDetailResponse,
            summary="Get restaurant detail")
async def get_restaurant(restaurant_id: uuid.UUID, rest_svc: RestSvc) -> RestaurantDetailResponse:
    return await rest_svc.get_restaurant(restaurant_id)


@router.get("/by-slug/{slug}", response_model=RestaurantDetailResponse,
            summary="Get restaurant by slug")
async def get_by_slug(slug: str, rest_svc: RestSvc) -> RestaurantDetailResponse:
    return await rest_svc.get_restaurant_by_slug(slug)


@router.get("/{restaurant_id}/coupons", response_model=list[CouponResponse],
            summary="Get active coupons for a restaurant")
async def get_coupons(restaurant_id: uuid.UUID, rest_svc: RestSvc) -> list[CouponResponse]:
    return await rest_svc.list_coupons(restaurant_id)


@router.post("/coupons/validate", response_model=CouponDiscountResponse,
             summary="Validate a coupon code and calculate discount")
async def validate_coupon(
    body: ValidateCouponRequest, rest_svc: RestSvc,
) -> CouponDiscountResponse:
    return await rest_svc.validate_coupon(body)
