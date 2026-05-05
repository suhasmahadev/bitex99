"""
Reviews router — create and list reviews.
Prefix: /api/v1/reviews
"""

import uuid

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.dependencies import CurrentUser, RevSvc
from app.schemas.review import CreateReviewRequest, ReviewResponse
from app.services.order_service import OrderServiceError
from app.utils.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/reviews", tags=["Reviews"])


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a review for a delivered order",
)
async def create_review(
    body: CreateReviewRequest,
    current_user: CurrentUser,
    rev_svc: RevSvc,
) -> ReviewResponse | JSONResponse:
    try:
        return await rev_svc.create_review(current_user.id, body)
    except OrderServiceError as e:
        return JSONResponse(status_code=e.status_code, content=e.body)


@router.get(
    "/restaurant/{restaurant_id}",
    summary="List all reviews for a restaurant (paginated)",
)
async def list_restaurant_reviews(
    restaurant_id: uuid.UUID,
    rev_svc: RevSvc,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
) -> PaginatedResponse:
    params = PaginationParams(page=page, page_size=limit)
    return await rev_svc.list_restaurant_reviews(restaurant_id, params)
