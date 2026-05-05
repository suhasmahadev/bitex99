"""
Menu router — browse menu items grouped by category.
Public endpoint.
"""
import uuid
from fastapi import APIRouter, Query
from app.dependencies import MenuSvc
from app.schemas.menu import MenuCategoryResponse, MenuItemResponse

router = APIRouter(prefix="/api/v1/restaurants", tags=["Menu"])


@router.get("/{restaurant_id}/menu", response_model=list[MenuCategoryResponse],
            summary="Get full menu grouped by category")
async def get_menu(
    restaurant_id: uuid.UUID,
    menu_svc: MenuSvc,
    category: str | None = Query(None, description="Filter by category name"),
    is_veg: bool | None = Query(None, description="Filter veg/non-veg items"),
    is_available: bool | None = Query(None, description="Filter available/unavailable items"),
) -> list[MenuCategoryResponse]:
    return await menu_svc.get_menu(
        restaurant_id,
        category=category,
        is_veg=is_veg,
        is_available=is_available,
    )


@router.get("/menu-items/{item_id}", response_model=MenuItemResponse,
            summary="Get a single menu item")
async def get_menu_item(item_id: uuid.UUID, menu_svc: MenuSvc) -> MenuItemResponse:
    return await menu_svc.get_menu_item(item_id)
