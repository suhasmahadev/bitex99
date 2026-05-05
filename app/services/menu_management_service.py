import os
import time
import uuid
import asyncio
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import MenuCategory, MenuItem
from app.models.restaurant_partner import RestaurantPartner

class MenuManagementService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def verify_restaurant_ownership(self, restaurant_id: uuid.UUID, partner_id: uuid.UUID):
        partner = await self._db.scalar(select(RestaurantPartner).where(RestaurantPartner.id == partner_id))
        if not partner or partner.restaurant_id != restaurant_id:
            raise HTTPException(status_code=403, detail="Not your restaurant")
        return partner

    async def get_categories(self, restaurant_id: uuid.UUID):
        categories = await self._db.scalars(
            select(MenuCategory)
            .where(MenuCategory.restaurant_id == restaurant_id, MenuCategory.is_active == True)
            .order_by(MenuCategory.display_order.asc())
        )
        return categories.all()

    async def create_category(self, restaurant_id: uuid.UUID, partner_id: uuid.UUID, name: str, display_order: int):
        await self.verify_restaurant_ownership(restaurant_id, partner_id)
        cat = MenuCategory(
            restaurant_id=restaurant_id,
            name=name,
            display_order=display_order,
            is_active=True
        )
        self._db.add(cat)
        await self._db.commit()
        await self._db.refresh(cat)
        return cat

    async def update_category(self, category_id: uuid.UUID, partner_id: uuid.UUID, data: dict):
        cat = await self._db.scalar(select(MenuCategory).where(MenuCategory.id == category_id))
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        await self.verify_restaurant_ownership(cat.restaurant_id, partner_id)
        
        for k, v in data.items():
            if v is not None and hasattr(cat, k):
                setattr(cat, k, v)
        
        await self._db.commit()
        await self._db.refresh(cat)
        return cat

    async def delete_category(self, category_id: uuid.UUID, partner_id: uuid.UUID):
        cat = await self._db.scalar(select(MenuCategory).where(MenuCategory.id == category_id))
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        await self.verify_restaurant_ownership(cat.restaurant_id, partner_id)

        active_item_count = await self._db.scalar(
            select(func.count(MenuItem.id)).where(
                MenuItem.category_id == category_id,
                ~MenuItem.tags.any("_deleted"),
            )
        )

        if active_item_count:
            raise HTTPException(status_code=409, detail={
                "error_code": "CATEGORY_HAS_ITEMS",
                "item_count": active_item_count,
                "message": "Move or delete items before deleting category"
            })
            
        await self._db.delete(cat)
        await self._db.commit()
        return {"message": "Category deleted"}

    async def get_items(self, restaurant_id: uuid.UUID, category_id: uuid.UUID = None, is_available: bool = None, search: str = None):
        q = select(MenuItem).where(MenuItem.restaurant_id == restaurant_id)
        if category_id:
            q = q.where(MenuItem.category_id == category_id)
        if is_available is not None:
            q = q.where(MenuItem.is_available == is_available)
        if search:
            q = q.where(MenuItem.name.ilike(f"%{search}%"))
            
        q = q.order_by(MenuItem.category_id, MenuItem.name)
        items = await self._db.scalars(q)
        result = []
        for item in items.all():
            if item.tags and "_deleted" in item.tags:
                continue
            item_dict = {
                "id": item.id,
                "restaurant_id": item.restaurant_id,
                "category_id": item.category_id,
                "name": item.name,
                "description": item.description,
                "price": item.price,
                "discounted_price": item.discounted_price,
                "effective_price": item.discounted_price if item.discounted_price else item.price,
                "is_veg": item.is_veg,
                "is_available": item.is_available,
                "preparation_time": item.preparation_time,
                "tags": item.tags,
                "image_url": item.image_url
            }
            result.append(item_dict)
        return result

    async def create_item(self, restaurant_id: uuid.UUID, partner_id: uuid.UUID, data: dict):
        await self.verify_restaurant_ownership(restaurant_id, partner_id)
        
        cat = await self._db.scalar(select(MenuCategory).where(
            MenuCategory.id == data["category_id"],
            MenuCategory.restaurant_id == restaurant_id
        ))
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found for this restaurant")
            
        item = MenuItem(restaurant_id=restaurant_id, **data)
        self._db.add(item)
        await self._db.commit()
        await self._db.refresh(item)
        
        effective_price = item.discounted_price if item.discounted_price else item.price
        return {**{c.name: getattr(item, c.name) for c in item.__table__.columns}, "effective_price": effective_price}

    async def update_item(self, item_id: uuid.UUID, partner_id: uuid.UUID, data: dict):
        item = await self._db.scalar(select(MenuItem).where(MenuItem.id == item_id))
        if not item or (item.tags and "_deleted" in item.tags):
            raise HTTPException(status_code=404, detail="Item not found")
            
        await self.verify_restaurant_ownership(item.restaurant_id, partner_id)
        
        if "category_id" in data and data["category_id"] is not None:
            cat = await self._db.scalar(select(MenuCategory).where(
                MenuCategory.id == data["category_id"],
                MenuCategory.restaurant_id == item.restaurant_id
            ))
            if not cat:
                raise HTTPException(status_code=404, detail="Category not found for this restaurant")
                
        for k, v in data.items():
            if v is not None and hasattr(item, k):
                setattr(item, k, v)
                
        await self._db.commit()
        await self._db.refresh(item)
        effective_price = item.discounted_price if item.discounted_price else item.price
        return {**{c.name: getattr(item, c.name) for c in item.__table__.columns}, "effective_price": effective_price}

    async def toggle_availability(self, item_id: uuid.UUID, partner_id: uuid.UUID, is_available: bool):
        item = await self._db.scalar(select(MenuItem).where(MenuItem.id == item_id))
        if not item or (item.tags and "_deleted" in item.tags):
            raise HTTPException(status_code=404, detail="Item not found")
        await self.verify_restaurant_ownership(item.restaurant_id, partner_id)
        
        item.is_available = is_available
        await self._db.commit()
        return {"id": item.id, "name": item.name, "is_available": is_available}

    async def bulk_toggle(self, item_ids: list[uuid.UUID], partner_id: uuid.UUID, is_available: bool):
        partner = await self._db.scalar(select(RestaurantPartner).where(RestaurantPartner.id == partner_id))
        
        result = await self._db.execute(
            update(MenuItem)
            .where(MenuItem.id.in_(item_ids), MenuItem.restaurant_id == partner.restaurant_id)
            .values(is_available=is_available)
        )
        await self._db.commit()
        return {"updated_count": result.rowcount}

    async def delete_item(self, item_id: uuid.UUID, partner_id: uuid.UUID):
        item = await self._db.scalar(select(MenuItem).where(MenuItem.id == item_id))
        if not item or (item.tags and "_deleted" in item.tags):
            raise HTTPException(status_code=404, detail="Item not found")
        await self.verify_restaurant_ownership(item.restaurant_id, partner_id)
        
        item.is_available = False
        tags = list(item.tags) if item.tags else []
        tags.append("_deleted")
        item.tags = tags
        
        await self._db.commit()
        return {"message": "Item removed from menu"}

    async def upload_item_image(self, item_id: uuid.UUID, partner_id: uuid.UUID, file: UploadFile):
        item = await self._db.scalar(select(MenuItem).where(MenuItem.id == item_id))
        if not item or (item.tags and "_deleted" in item.tags):
            raise HTTPException(status_code=404, detail="Item not found")
        await self.verify_restaurant_ownership(item.restaurant_id, partner_id)
        
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="INVALID_FILE_TYPE")

        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="FILE_TOO_LARGE")
            
        ext = "jpg"
        if file.filename:
            ext = file.filename.split('.')[-1].lower()
            
        directory = f"uploads/menu/{item.restaurant_id}/"
        os.makedirs(directory, exist_ok=True)
        filename = f"{item_id}_{int(time.time())}.{ext}"
        filepath = os.path.join(directory, filename)
        
        await asyncio.to_thread(Path(filepath).write_bytes, content)
            
        item.image_url = f"/{directory}{filename}"
        await self._db.commit()
        await self._db.refresh(item)
        effective_price = item.discounted_price if item.discounted_price else item.price
        return {**{c.name: getattr(item, c.name) for c in item.__table__.columns}, "effective_price": effective_price}
