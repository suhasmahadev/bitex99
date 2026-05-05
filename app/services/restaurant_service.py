"""
Restaurant service: discovery, search, filtering, and coupon validation.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    CouponNotFoundError,
    InvalidCouponError,
    RestaurantNotFoundError,
)
from app.models.coupon import Coupon
from app.models.restaurant import Restaurant
from app.schemas.restaurant import (
    CouponDiscountResponse,
    CouponResponse,
    RestaurantDetailResponse,
    RestaurantListResponse,
    RestaurantSearchParams,
    ValidateCouponRequest,
)
from app.utils.pagination import PaginatedResponse, PaginationParams


class RestaurantService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_restaurants(
        self,
        params: RestaurantSearchParams,
        pagination: PaginationParams,
    ) -> PaginatedResponse:
        query = select(
            Restaurant.id,
            Restaurant.name,
            Restaurant.slug,
            Restaurant.image_url,
            Restaurant.cuisine_types,
            Restaurant.city,
            Restaurant.rating,
            Restaurant.total_reviews,
            Restaurant.avg_delivery_time,
            Restaurant.min_order_amount,
            Restaurant.is_pure_veg,
            Restaurant.is_open,
            Restaurant.has_offers,
        )
        query = self._apply_filters(query, params)
        query = self._apply_sorting(query, params)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        # Paginate
        query = query.offset(pagination.offset).limit(pagination.limit)
        result = await self._db.execute(query)
        restaurants = result.mappings().all()

        items = [RestaurantListResponse.model_validate(dict(r)) for r in restaurants]
        return PaginatedResponse.create(items, total, pagination)

    async def get_restaurant(self, restaurant_id: uuid.UUID) -> RestaurantDetailResponse:
        result = await self._db.execute(
            select(Restaurant).where(Restaurant.id == restaurant_id)
        )
        restaurant = result.scalar_one_or_none()
        if restaurant is None:
            raise RestaurantNotFoundError()
        return RestaurantDetailResponse.model_validate(restaurant)

    async def get_restaurant_by_slug(self, slug: str) -> RestaurantDetailResponse:
        result = await self._db.execute(
            select(Restaurant).where(Restaurant.slug == slug)
        )
        restaurant = result.scalar_one_or_none()
        if restaurant is None:
            raise RestaurantNotFoundError()
        return RestaurantDetailResponse.model_validate(restaurant)

    # ── Coupon ────────────────────────────────────────────────────────────────

    async def validate_coupon(self, data: ValidateCouponRequest) -> CouponDiscountResponse:
        result = await self._db.execute(
            select(Coupon).where(Coupon.code == data.code.upper())
        )
        coupon = result.scalar_one_or_none()
        if coupon is None:
            raise CouponNotFoundError()

        # Validate active
        if not coupon.is_active:
            raise InvalidCouponError(detail="This coupon is no longer active")

        # Validate expiry
        now = datetime.now(UTC)
        if coupon.valid_until and coupon.valid_until.replace(tzinfo=None) < now.replace(tzinfo=None):
            raise InvalidCouponError(detail="This coupon has expired")

        # Validate usage limit
        if coupon.usage_limit is not None and coupon.times_used >= coupon.usage_limit:
            raise InvalidCouponError(detail="Coupon usage limit reached")

        # Validate minimum order
        if data.order_amount < coupon.min_order_amount:
            raise InvalidCouponError(
                detail=f"Minimum order amount is ₹{coupon.min_order_amount}"
            )

        # Validate restaurant-specific coupon
        if coupon.restaurant_id and data.restaurant_id:
            if coupon.restaurant_id != data.restaurant_id:
                raise InvalidCouponError(detail="This coupon is not valid for this restaurant")

        # Calculate discount
        if coupon.discount_type == "percentage":
            discount = data.order_amount * (coupon.discount_value / 100)
            if coupon.max_discount:
                discount = min(discount, coupon.max_discount)
        else:
            discount = min(coupon.discount_value, data.order_amount)

        return CouponDiscountResponse(
            code=coupon.code,
            discount_type=coupon.discount_type,
            discount_value=coupon.discount_value,
            calculated_discount=round(discount, 2),
            final_amount=round(data.order_amount - discount, 2),
        )

    async def list_coupons(self, restaurant_id: uuid.UUID | None = None) -> list[CouponResponse]:
        query = select(Coupon).where(Coupon.is_active.is_(True))
        now = datetime.now(UTC)
        if restaurant_id:
            query = query.where(
                (Coupon.restaurant_id == restaurant_id) | (Coupon.restaurant_id.is_(None))
            )
        result = await self._db.execute(query)
        return [CouponResponse.model_validate(c) for c in result.scalars().all()]

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _apply_filters(query: Select, params: RestaurantSearchParams) -> Select:
        if params.q:
            search = f"%{params.q}%"
            query = query.where(
                Restaurant.name.ilike(search)
                | Restaurant.cuisine_types.any(params.q)
            )
        if params.city:
            query = query.where(Restaurant.city.ilike(f"%{params.city}%"))
        if params.cuisine:
            query = query.where(Restaurant.cuisine_types.any(params.cuisine))
        if params.is_veg_only is not None:
            query = query.where(Restaurant.is_pure_veg == params.is_veg_only)
        if params.is_open is not None:
            query = query.where(Restaurant.is_open == params.is_open)
        if params.min_rating is not None:
            query = query.where(Restaurant.rating >= params.min_rating)
        return query

    @staticmethod
    def _apply_sorting(query: Select, params: RestaurantSearchParams) -> Select:
        sort_columns = {
            "avg_rating": Restaurant.rating,
            "cost_for_two": Restaurant.min_order_amount,
            "avg_delivery_time_min": Restaurant.avg_delivery_time,
            "name": Restaurant.name,
        }
        col = sort_columns.get(params.sort_by, Restaurant.rating)
        if params.sort_order == "asc":
            query = query.order_by(col.asc())
        else:
            query = query.order_by(col.desc())
        return query
