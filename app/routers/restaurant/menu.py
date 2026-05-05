import uuid

from fastapi import APIRouter, File, Form, UploadFile, Query
from app.dependencies import DB, CurrentUser, ApprovedRestaurant
from app.schemas.restaurant_menu import (
    CategoryCreateRequest, CategoryUpdateRequest,
    MenuItemCreateRequest, MenuItemUpdateRequest,
    MenuItemToggleRequest, MenuItemBulkToggleRequest
)
from app.services.menu_management_service import MenuManagementService

router = APIRouter(prefix="/api/v1/restaurant/menu", tags=["Restaurant Menu Management"])

@router.get("/categories")
async def get_categories(
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = MenuManagementService(db)
    return await svc.get_categories(partner.restaurant_id)

@router.post("/categories")
async def create_category(
    body: CategoryCreateRequest,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = MenuManagementService(db)
    return await svc.create_category(
        restaurant_id=partner.restaurant_id,
        partner_id=partner.id,
        name=body.name,
        display_order=body.display_order
    )

@router.patch("/categories/{category_id}")
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdateRequest,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = MenuManagementService(db)
    return await svc.update_category(
        category_id=category_id,
        partner_id=partner.id,
        data=body.model_dump(exclude_unset=True)
    )

@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = MenuManagementService(db)
    return await svc.delete_category(category_id=category_id, partner_id=partner.id)

@router.get("/items")
async def get_items(
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant,
    category_id: uuid.UUID = Query(None),
    is_available: bool = Query(None),
    search: str = Query(None)
):
    svc = MenuManagementService(db)
    return await svc.get_items(
        restaurant_id=partner.restaurant_id,
        category_id=category_id,
        is_available=is_available,
        search=search
    )

@router.post("/items")
async def create_item(
    body: MenuItemCreateRequest,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = MenuManagementService(db)
    return await svc.create_item(
        restaurant_id=partner.restaurant_id,
        partner_id=partner.id,
        data=body.model_dump()
    )

@router.patch("/items/{item_id}")
async def update_item(
    item_id: uuid.UUID,
    body: MenuItemUpdateRequest,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = MenuManagementService(db)
    return await svc.update_item(
        item_id=item_id,
        partner_id=partner.id,
        data=body.model_dump(exclude_unset=True)
    )

@router.delete("/items/{item_id}")
async def delete_item(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = MenuManagementService(db)
    return await svc.delete_item(item_id=item_id, partner_id=partner.id)

@router.patch("/items/{item_id}/toggle")
async def toggle_availability(
    item_id: uuid.UUID,
    body: MenuItemToggleRequest,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = MenuManagementService(db)
    return await svc.toggle_availability(
        item_id=item_id,
        partner_id=partner.id,
        is_available=body.is_available
    )

@router.post("/items/{item_id}/image")
async def upload_item_image(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant,
    file: UploadFile = File(...)
):
    svc = MenuManagementService(db)
    return await svc.upload_item_image(
        item_id=item_id,
        partner_id=partner.id,
        file=file
    )

@router.post("/bulk-toggle")
async def bulk_toggle(
    body: MenuItemBulkToggleRequest,
    current_user: CurrentUser,
    db: DB,
    partner: ApprovedRestaurant
):
    svc = MenuManagementService(db)
    return await svc.bulk_toggle(
        item_ids=body.item_ids,
        partner_id=partner.id,
        is_available=body.is_available
    )
