"""
Orders router — place, track, cancel, and list orders.
Prefix: /api/v1/orders — all endpoints require authentication.
Thin wiring only — all business logic in OrderService.
"""

import uuid

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.dependencies import CurrentUser, OrdSvc
from app.schemas.order import (
    CancelOrderRequest,
    OrderResponse,
    PlaceOrderRequest,
    UpdateOrderStatusRequest,
)
from app.services.order_service import OrderServiceError
from app.utils.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


@router.post(
    "/place",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Place a new order from cart",
)
async def place_order(
    body: PlaceOrderRequest,
    current_user: CurrentUser,
    order_svc: OrdSvc,
) -> OrderResponse | JSONResponse:
    try:
        return await order_svc.place_order(current_user.id, body)
    except OrderServiceError as e:
        return JSONResponse(status_code=e.status_code, content=e.body)


@router.get("", summary="List my orders")
async def list_orders(
    current_user: CurrentUser,
    order_svc: OrdSvc,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
) -> PaginatedResponse | dict:
    params = PaginationParams(page=page, page_size=limit)
    return await order_svc.list_orders(current_user.id, params, status_filter)


@router.get("/{order_id}", response_model=OrderResponse, summary="Get order detail")
async def get_order(
    order_id: uuid.UUID,
    current_user: CurrentUser,
    order_svc: OrdSvc,
) -> OrderResponse:
    return await order_svc.get_order(current_user.id, order_id)


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel an order (if cancellable)",
)
async def cancel_order(
    order_id: uuid.UUID,
    body: CancelOrderRequest,
    current_user: CurrentUser,
    order_svc: OrdSvc,
) -> OrderResponse | JSONResponse:
    try:
        return await order_svc.cancel_order(current_user.id, order_id, body)
    except OrderServiceError as e:
        return JSONResponse(status_code=e.status_code, content=e.body)


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status (webhook/internal use)",
)
async def update_status(
    order_id: uuid.UUID,
    body: UpdateOrderStatusRequest,
    order_svc: OrdSvc,
) -> OrderResponse | JSONResponse:
    try:
        return await order_svc.update_status(order_id, body.status)
    except OrderServiceError as e:
        return JSONResponse(status_code=e.status_code, content=e.body)
