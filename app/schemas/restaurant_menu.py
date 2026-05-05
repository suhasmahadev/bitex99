from pydantic import BaseModel
import uuid
from typing import Optional, List

class CategoryCreateRequest(BaseModel):
    name: str
    display_order: int = 0

class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class MenuItemCreateRequest(BaseModel):
    category_id: uuid.UUID
    name: str
    description: Optional[str] = None
    price: float
    discounted_price: Optional[float] = None
    is_veg: bool
    is_available: bool = True
    preparation_time: Optional[int] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None

class MenuItemUpdateRequest(BaseModel):
    category_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    discounted_price: Optional[float] = None
    is_veg: Optional[bool] = None
    is_available: Optional[bool] = None
    preparation_time: Optional[int] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None

class MenuItemToggleRequest(BaseModel):
    is_available: bool

class MenuItemBulkToggleRequest(BaseModel):
    item_ids: List[uuid.UUID]
    is_available: bool
