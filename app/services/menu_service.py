"""
Menu service: browse menu items by restaurant, group by category.
"""

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import RestaurantNotFoundError
from app.models.menu import MenuItem
from app.models.restaurant import Restaurant
from app.schemas.menu import MenuCategoryResponse, MenuItemResponse


class MenuService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_menu(
        self,
        restaurant_id: uuid.UUID,
        category: str | None = None,
        is_veg: bool | None = None,
        is_available: bool | None = None,
    ) -> list[MenuCategoryResponse]:
        """Get menu items grouped by category for a restaurant."""
        # Verify restaurant exists
        rest_result = await self._db.execute(
            select(Restaurant.id).where(Restaurant.id == restaurant_id)
        )
        if rest_result.scalar_one_or_none() is None:
            raise RestaurantNotFoundError()

        from app.models.menu import MenuCategory
        
        query = (
            select(MenuCategory)
            .where(MenuCategory.restaurant_id == restaurant_id)
            .where(MenuCategory.is_active == True)
            .order_by(MenuCategory.display_order.asc())
        )
        cat_result = await self._db.execute(query)
        categories = cat_result.scalars().all()
        
        cat_ids = [c.id for c in categories]
        if not cat_ids:
            return []
            
        items_query = (
            select(MenuItem)
            .where(MenuItem.category_id.in_(cat_ids))
            .order_by(MenuItem.name.asc())
        )
        if is_veg is not None:
            items_query = items_query.where(MenuItem.is_veg == is_veg)
        if is_available is not None:
            items_query = items_query.where(MenuItem.is_available == is_available)
            
        items_result = await self._db.execute(items_query)
        items = items_result.scalars().all()
        
        grouped = defaultdict(list)
        for item in items:
            if not (item.tags and "_deleted" in item.tags):
                grouped[item.category_id].append(item)
            
        result = []
        for cat in categories:
            cat_items = grouped.get(cat.id, [])
            if cat_items:
                result.append(
                    MenuCategoryResponse(
                        category=cat.name,
                        items=[MenuItemResponse.model_validate(i) for i in cat_items]
                    )
                )

        return result

    async def get_menu_item(self, item_id: uuid.UUID) -> MenuItemResponse:
        result = await self._db.execute(
            select(MenuItem).where(MenuItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            from app.exceptions import MenuItemNotFoundError
            raise MenuItemNotFoundError()
        return MenuItemResponse.model_validate(item)
