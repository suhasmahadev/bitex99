"""
Review service — create reviews and list per restaurant.

CRITICAL RULE: Restaurant rating is updated with ONE atomic SQL UPDATE.
We NEVER fetch rating to Python, calculate, then write back — that creates
a race condition under concurrent review inserts.
"""

import uuid

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ForbiddenError, OrderNotFoundError, ReviewAlreadyExistsError
from app.models.order import Order, OrderStatus
from app.models.restaurant import Restaurant
from app.models.review import Review
from app.models.user import User
from app.schemas.review import CreateReviewRequest, ReviewListItem, ReviewResponse
from app.services.order_service import OrderServiceError
from app.utils.pagination import PaginatedResponse, PaginationParams
from fastapi import status


class ReviewService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_review(
        self, user_id: uuid.UUID, data: CreateReviewRequest
    ) -> ReviewResponse:
        # Step 1: Fetch order, verify ownership
        res = await self._db.execute(
            select(Order).where(Order.id == data.order_id)
        )
        order = res.scalar_one_or_none()
        if order is None:
            raise OrderNotFoundError()
        if order.user_id != user_id:
            raise ForbiddenError()

        # Step 2: Order must be DELIVERED
        if order.status != OrderStatus.DELIVERED:
            raise OrderServiceError(
                status.HTTP_409_CONFLICT,
                {
                    "success": False,
                    "error_code": "ORDER_NOT_DELIVERED",
                    "message": "You can only review delivered orders",
                },
            )

        # Step 3: Check no existing review for this order
        existing = await self._db.execute(
            select(Review).where(Review.order_id == data.order_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ReviewAlreadyExistsError()

        # Step 4: Insert review
        review = Review(
            order_id=data.order_id,
            user_id=user_id,
            restaurant_id=order.restaurant_id,
            food_rating=data.food_rating,
            delivery_rating=data.delivery_rating,
            comment=data.comment,
        )
        self._db.add(review)
        await self._db.flush()
        await self._db.refresh(review)  # populate server_default created_at

        # Step 5: Atomically recalculate restaurant rating in ONE UPDATE statement.
        # new_avg = (food_rating + delivery_rating) / 2
        # new_rating = (old_rating * old_count + new_avg) / (old_count + 1)
        # This never fetches rating to Python — the arithmetic is done in the DB.
        # Use sqlalchemy literal() to avoid Decimal/float type mismatch.
        from decimal import Decimal
        from sqlalchemy import literal
        new_avg_dec = Decimal(str((data.food_rating + data.delivery_rating) / 2.0))
        await self._db.execute(
            update(Restaurant)
            .where(Restaurant.id == order.restaurant_id)
            .values(
                rating=(
                    (Restaurant.rating * Restaurant.total_reviews + literal(new_avg_dec))
                    / (Restaurant.total_reviews + 1)
                ),
                total_reviews=Restaurant.total_reviews + 1,
            )
            .execution_options(synchronize_session="fetch")
        )

        # Step 6: Return review
        return ReviewResponse(
            id=review.id,
            order_id=review.order_id,
            restaurant_id=review.restaurant_id,
            food_rating=review.food_rating,
            delivery_rating=review.delivery_rating,
            comment=review.comment,
            created_at=review.created_at,
        )

    async def list_restaurant_reviews(
        self,
        restaurant_id: uuid.UUID,
        pagination: PaginationParams,
    ) -> PaginatedResponse:
        count_res = await self._db.execute(
            select(func.count(Review.id)).where(Review.restaurant_id == restaurant_id)
        )
        total = count_res.scalar_one()

        result = await self._db.execute(
            select(Review, User.name.label("user_name"))
            .join(User, User.id == Review.user_id)
            .where(Review.restaurant_id == restaurant_id)
            .order_by(Review.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        rows = result.all()

        items = []
        for row in rows:
            review_obj = row[0]
            user_name = row[1]
            # First name only
            first_name = user_name.split()[0] if user_name else None
            items.append(
                ReviewListItem(
                    id=review_obj.id,
                    food_rating=review_obj.food_rating,
                    delivery_rating=review_obj.delivery_rating,
                    comment=review_obj.comment,
                    created_at=review_obj.created_at,
                    user_first_name=first_name,
                )
            )

        return PaginatedResponse.create(items, total, pagination)

    async def respond_to_review(
        self,
        review_id: uuid.UUID,
        restaurant_id: uuid.UUID,
        response_text: str,
    ) -> dict:
        result = await self._db.execute(select(Review).where(Review.id == review_id))
        review = result.scalar_one_or_none()
        if review is None:
            raise OrderServiceError(
                status.HTTP_404_NOT_FOUND,
                {"success": False, "error_code": "NOT_FOUND", "message": "Review not found"},
            )
        if review.restaurant_id != restaurant_id:
            raise ForbiddenError()
        review.response_text = response_text
        await self._db.flush()
        return {
            "review_id": str(review.id),
            "response_text": review.response_text,
            "message": "Response saved",
        }
