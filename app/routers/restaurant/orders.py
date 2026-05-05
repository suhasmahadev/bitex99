"""
Restaurant Orders router — live order management, status transitions.
Auth: ApprovedRestaurant (DOCS_APPROVED status required).
"""
import uuid

from fastapi import APIRouter, HTTPException, Query
from app.dependencies import DB, CurrentUser, ApprovedRestaurant
from app.schemas.restaurant_orders import AcceptOrderRequest, RejectOrderRequest
from app.services.order_management_service import OrderManagementService
from app.redis_client import get_redis

router = APIRouter(prefix="/api/v1/restaurant/orders", tags=["Restaurant Orders"])

VALID_REJECT_REASONS = {"OUT_OF_STOCK", "RESTAURANT_CLOSING", "HIGH_DEMAND", "OTHER"}


@router.get("/live")
async def get_live_orders(
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant,
):
    svc = OrderManagementService(db)
    return await svc.get_live_orders(partner.restaurant_id)


@router.get("/pending")
async def get_pending_orders(
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant,
):
    svc = OrderManagementService(db)
    live = await svc.get_live_orders(partner.restaurant_id)
    return live.get("placed", [])


@router.get("")
async def get_orders(
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant,
    status: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    svc = OrderManagementService(db)
    return await svc.get_orders(
        restaurant_id=partner.restaurant_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        search=search,
        page=page,
        limit=limit,
    )


@router.get("/{order_id}")
async def get_order_detail(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant,
):
    svc = OrderManagementService(db)
    return await svc.get_order_detail(order_id, partner.restaurant_id)


@router.post("/{order_id}/accept")
async def accept_order(
    order_id: uuid.UUID,
    body: AcceptOrderRequest,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant,
):
    if not (5 <= body.preparation_time <= 120):
        raise HTTPException(status_code=422, detail="preparation_time must be 5–120 minutes")
    redis = get_redis()
    svc = OrderManagementService(db)
    return await svc.accept_order(order_id, partner.restaurant_id, body.preparation_time, redis)


@router.post("/{order_id}/reject")
async def reject_order(
    order_id: uuid.UUID,
    body: RejectOrderRequest,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant,
):
    if body.reason not in VALID_REJECT_REASONS:
        raise HTTPException(
            status_code=422,
            detail=f"reason must be one of {VALID_REJECT_REASONS}",
        )
    svc = OrderManagementService(db)
    return await svc.reject_order(order_id, partner.restaurant_id, body.reason, body.description)


@router.post("/{order_id}/preparing")
async def mark_preparing(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant,
):
    svc = OrderManagementService(db)
    return await svc.mark_preparing(order_id, partner.restaurant_id)


@router.post("/{order_id}/ready")
async def mark_ready(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant,
):
    svc = OrderManagementService(db)
    return await svc.mark_ready(order_id, partner.restaurant_id)
