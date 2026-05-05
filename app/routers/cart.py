"""
Cart router — thin HTTP wiring only. All logic lives in CartService.
Prefix: /api/v1/cart — all endpoints require authentication.
"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.dependencies import CurrentUser, CartSvc
from app.schemas.cart import (
    AddToCartRequest,
    CartResponse,
    RemoveFromCartRequest,
    UpdateQuantityRequest,
)
from app.services.cart_service import CartConflictError, ItemUnavailableError

router = APIRouter(prefix="/api/v1/cart", tags=["Cart"])


@router.get("", response_model=CartResponse, summary="Get my cart")
async def get_cart(current_user: CurrentUser, cart_svc: CartSvc) -> CartResponse:
    return await cart_svc.get_cart(current_user.id)


@router.post("/add", response_model=CartResponse, summary="Add item to cart")
async def add_item(
    body: AddToCartRequest,
    current_user: CurrentUser,
    cart_svc: CartSvc,
) -> CartResponse | JSONResponse:
    try:
        return await cart_svc.add_item(current_user.id, body)
    except CartConflictError as e:
        body = e.response.model_dump()
        body["details"] = body.get("data")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=body,
        )
    except ItemUnavailableError:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "error_code": "ITEM_UNAVAILABLE",
                "message": "This item is currently unavailable",
            },
        )


@router.post(
    "/update-quantity",
    response_model=CartResponse,
    summary="Update item quantity (0 = remove)",
)
async def update_quantity(
    body: UpdateQuantityRequest,
    current_user: CurrentUser,
    cart_svc: CartSvc,
) -> CartResponse:
    return await cart_svc.update_quantity(current_user.id, body)


@router.post("/remove", response_model=CartResponse, summary="Remove item from cart")
async def remove_item(
    body: RemoveFromCartRequest,
    current_user: CurrentUser,
    cart_svc: CartSvc,
) -> CartResponse:
    return await cart_svc.remove_item(current_user.id, body)


@router.post("/clear", response_model=CartResponse, summary="Clear entire cart")
async def clear_cart(current_user: CurrentUser, cart_svc: CartSvc) -> CartResponse:
    return await cart_svc.clear_cart(current_user.id)
