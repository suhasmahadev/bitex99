import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.dependencies import ApprovedRestaurant, DB
from app.models.review import Review
from app.models.user import User
from app.services.restaurant_analytics_service import RestaurantAnalyticsService

router = APIRouter(prefix="/api/v1/restaurant/reviews", tags=["Restaurant Reviews"])


class ReviewResponseRequest(BaseModel):
    response: str = Field(min_length=1, max_length=500)


@router.get("")
async def get_reviews(
    partner: ApprovedRestaurant,
    db: DB,
    rating: int | None = Query(None, ge=1, le=5),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
):
    conditions = [Review.restaurant_id == partner.restaurant_id]
    if rating is not None:
        conditions.append(func.floor((Review.food_rating + Review.delivery_rating) / 2) == rating)

    total = await db.scalar(select(func.count(Review.id)).where(*conditions)) or 0
    rows = (
        await db.execute(
            select(Review, User.name.label("customer_name"))
            .join(User, User.id == Review.user_id)
            .where(*conditions)
            .order_by(Review.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()

    items = []
    for review, customer_name in rows:
        items.append({
            "id": str(review.id),
            "order_id": str(review.order_id),
            "food_rating": review.food_rating,
            "delivery_rating": review.delivery_rating,
            "comment": review.comment,
            "response_text": review.response_text,
            "customer_name": customer_name.split()[0] if customer_name else None,
            "created_at": review.created_at.isoformat() if review.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit if limit else 1,
    }


@router.get("/stats")
async def review_stats(partner: ApprovedRestaurant, db: DB):
    return await RestaurantAnalyticsService().get_ratings_summary(partner.restaurant_id, db)


@router.post("/{review_id}/respond")
async def respond_to_review(
    review_id: uuid.UUID,
    body: ReviewResponseRequest,
    partner: ApprovedRestaurant,
    db: DB,
):
    review = await db.scalar(select(Review).where(Review.id == review_id))
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.restaurant_id != partner.restaurant_id:
        raise HTTPException(status_code=403, detail="Not your restaurant")

    review.response_text = body.response
    await db.flush()
    return {
        "review_id": str(review.id),
        "response_text": review.response_text,
        "message": "Response saved",
    }
