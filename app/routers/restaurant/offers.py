import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.dependencies import ApprovedRestaurant, DB
from app.models.restaurant_offer import OfferType
from app.services.restaurant_offer_service import RestaurantOfferService

router = APIRouter(prefix="/api/v1/restaurant/offers", tags=["Restaurant Offers"])


class OfferCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    offer_type: OfferType
    discount_value: float = Field(ge=0)
    max_discount: float | None = Field(default=None, ge=0)
    min_order_amount: float = Field(default=0, ge=0)
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class OfferUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    offer_type: OfferType | None = None
    discount_value: float | None = Field(default=None, ge=0)
    max_discount: float | None = Field(default=None, ge=0)
    min_order_amount: float | None = Field(default=None, ge=0)
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class OfferToggleRequest(BaseModel):
    is_active: bool


@router.get("")
async def get_offers(partner: ApprovedRestaurant, db: DB):
    return await RestaurantOfferService().get_offers(partner.restaurant_id, db)


@router.post("")
async def create_offer(body: OfferCreateRequest, partner: ApprovedRestaurant, db: DB):
    return await RestaurantOfferService().create_offer(
        partner.restaurant_id,
        partner.id,
        body.model_dump(exclude_unset=True),
        db,
    )


@router.patch("/{offer_id}")
async def update_offer(offer_id: uuid.UUID, body: OfferUpdateRequest, partner: ApprovedRestaurant, db: DB):
    return await RestaurantOfferService().update_offer(
        offer_id,
        partner.id,
        body.model_dump(exclude_unset=True),
        db,
    )


@router.patch("/{offer_id}/toggle")
async def toggle_offer(offer_id: uuid.UUID, body: OfferToggleRequest, partner: ApprovedRestaurant, db: DB):
    return await RestaurantOfferService().toggle_offer(offer_id, partner.id, body.is_active, db)


@router.delete("/{offer_id}")
async def delete_offer(offer_id: uuid.UUID, partner: ApprovedRestaurant, db: DB):
    return await RestaurantOfferService().delete_offer(offer_id, partner.id, db)
