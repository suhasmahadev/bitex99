import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import Restaurant
from app.models.restaurant_offer import RestaurantOffer
from app.models.restaurant_partner import RestaurantPartner


class RestaurantOfferService:
    async def _verify_partner(self, partner_id: uuid.UUID, restaurant_id: uuid.UUID, db: AsyncSession) -> None:
        partner = await db.scalar(select(RestaurantPartner).where(RestaurantPartner.id == partner_id))
        if not partner or partner.restaurant_id != restaurant_id:
            raise HTTPException(status_code=403, detail="Not your restaurant")

    async def _refresh_has_offers(self, restaurant_id: uuid.UUID, db: AsyncSession) -> None:
        active_count = await db.scalar(
            select(func.count(RestaurantOffer.id)).where(
                RestaurantOffer.restaurant_id == restaurant_id,
                RestaurantOffer.is_active.is_(True),
            )
        ) or 0
        await db.execute(
            update(Restaurant)
            .where(Restaurant.id == restaurant_id)
            .values(has_offers=active_count > 0)
        )

    def _serialize(self, offer: RestaurantOffer) -> dict:
        return {
            "id": str(offer.id),
            "restaurant_id": str(offer.restaurant_id),
            "title": offer.title,
            "offer_type": offer.offer_type.value if hasattr(offer.offer_type, "value") else str(offer.offer_type),
            "discount_value": float(offer.discount_value),
            "max_discount": float(offer.max_discount) if offer.max_discount is not None else None,
            "min_order_amount": float(offer.min_order_amount or 0),
            "valid_from": offer.valid_from.isoformat() if offer.valid_from else None,
            "valid_until": offer.valid_until.isoformat() if offer.valid_until else None,
            "is_active": offer.is_active,
            "usage_count": offer.usage_count,
        }

    async def get_offers(self, restaurant_id: uuid.UUID, db: AsyncSession) -> list[dict]:
        offers = await db.scalars(
            select(RestaurantOffer)
            .where(RestaurantOffer.restaurant_id == restaurant_id)
            .order_by(RestaurantOffer.created_at.desc())
        )
        return [self._serialize(offer) for offer in offers.all()]

    async def create_offer(self, restaurant_id: uuid.UUID, partner_id: uuid.UUID, data: dict, db: AsyncSession) -> dict:
        await self._verify_partner(partner_id, restaurant_id, db)
        offer = RestaurantOffer(restaurant_id=restaurant_id, **data)
        db.add(offer)
        await db.execute(update(Restaurant).where(Restaurant.id == restaurant_id).values(has_offers=True))
        await db.flush()
        await db.refresh(offer)
        return self._serialize(offer)

    async def update_offer(self, offer_id: uuid.UUID, partner_id: uuid.UUID, data: dict, db: AsyncSession) -> dict:
        offer = await db.scalar(select(RestaurantOffer).where(RestaurantOffer.id == offer_id))
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        await self._verify_partner(partner_id, offer.restaurant_id, db)
        for key, value in data.items():
            setattr(offer, key, value)
        await db.flush()
        await db.refresh(offer)
        await self._refresh_has_offers(offer.restaurant_id, db)
        return self._serialize(offer)

    async def toggle_offer(self, offer_id: uuid.UUID, partner_id: uuid.UUID, is_active: bool, db: AsyncSession) -> dict:
        offer = await db.scalar(select(RestaurantOffer).where(RestaurantOffer.id == offer_id))
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        await self._verify_partner(partner_id, offer.restaurant_id, db)
        offer.is_active = is_active
        await db.flush()
        await self._refresh_has_offers(offer.restaurant_id, db)
        return {"id": str(offer.id), "title": offer.title, "is_active": offer.is_active}

    async def delete_offer(self, offer_id: uuid.UUID, partner_id: uuid.UUID, db: AsyncSession) -> dict:
        offer = await db.scalar(select(RestaurantOffer).where(RestaurantOffer.id == offer_id))
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        await self._verify_partner(partner_id, offer.restaurant_id, db)
        offer.is_active = False
        await db.flush()
        await self._refresh_has_offers(offer.restaurant_id, db)
        return {"message": "Offer removed"}

    async def get_valid_offers_for_order(self, restaurant_id: uuid.UUID, order_amount: float, db: AsyncSession) -> list[dict]:
        now = datetime.now(UTC)
        offers = await db.scalars(
            select(RestaurantOffer).where(
                RestaurantOffer.restaurant_id == restaurant_id,
                RestaurantOffer.is_active.is_(True),
                (RestaurantOffer.valid_from.is_(None)) | (RestaurantOffer.valid_from <= now),
                (RestaurantOffer.valid_until.is_(None)) | (RestaurantOffer.valid_until >= now),
                RestaurantOffer.min_order_amount <= order_amount,
            )
        )
        return [self._serialize(offer) for offer in offers.all()]
