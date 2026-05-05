import random
import uuid
from datetime import time

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant import Restaurant
from app.models.restaurant_partner import RestaurantPartner
from app.models.restaurant_timing import RestaurantTiming
from app.models.order import Order
from app.models.user import User
from app.schemas.restaurant_partner import RestaurantSetupRequest
from app.utils.jwt import create_access_token


class RestaurantPartnerService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def setup_restaurant(
        self,
        user_id: uuid.UUID,
        data: RestaurantSetupRequest,
    ) -> dict:
        # 1. Check user has no existing restaurant_partners record
        existing = await self._db.scalar(
            select(RestaurantPartner).where(RestaurantPartner.user_id == user_id)
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "error_code": "RESTAURANT_ALREADY_EXISTS",
                    "message": "You already have a restaurant registered"
                }
            )

        # 2. Generate unique slug
        base_slug = data.restaurant_name.lower().replace(' ', '-').replace("'", '')
        slug = base_slug
        
        while True:
            exists = await self._db.scalar(select(Restaurant).where(Restaurant.slug == slug))
            if not exists:
                break
            slug = f"{base_slug}-{random.randint(1000, 9999)}"

        # 3. INSERT restaurants record
        new_restaurant = Restaurant(
            name=data.restaurant_name,
            slug=slug,
            description=data.description,
            cuisine_types=data.cuisine_types,
            city=data.city,
            full_address=data.full_address,
            latitude=data.latitude,
            longitude=data.longitude,
            phone=data.phone,
            is_open=False,
            min_order_amount=data.min_order_amount,
            avg_delivery_time=data.avg_delivery_time,
            delivery_fee=data.delivery_fee
        )
        self._db.add(new_restaurant)
        await self._db.flush()

        # 4. INSERT restaurant_partners record
        new_partner = RestaurantPartner(
            user_id=user_id,
            restaurant_id=new_restaurant.id,
            owner_name=data.owner_name,
            business_type=data.business_type,
            commission_rate=20.0,
            fssai_number=data.fssai_number,
            fssai_expiry=data.fssai_expiry,
            gstin=data.gstin,
            pan_number=data.pan_number,
            bank_account_number=data.bank_account_number,
            bank_ifsc=data.bank_ifsc,
            bank_account_name=data.bank_account_name
        )
        self._db.add(new_partner)
        await self._db.flush()

        # 5. INSERT restaurant_timings for all 7 days
        for day in range(7):
            timing = RestaurantTiming(
                restaurant_id=new_restaurant.id,
                day_of_week=day,
                opens_at=time(10, 0),
                closes_at=time(23, 0),
                is_closed=False
            )
            self._db.add(timing)

        # Update User status if needed
        # user = await self._db.scalar(select(User).where(User.id == user_id))
        # Wait, the spec says to return next_step etc.
        await self._db.commit()

        # 6. Update JWT — re-issue tokens with restaurant_id
        # Need user phone and role
        user = await self._db.scalar(select(User).where(User.id == user_id))
        
        new_access = create_access_token(
            user_id=user_id,
            phone=user.phone,
            role=user.role,
            restaurant_partner_id=new_partner.id,
            restaurant_id=new_restaurant.id
        )

        return {
            "restaurant_id": new_restaurant.id,
            "partner_id": new_partner.id,
            "slug": slug,
            "new_access_token": new_access,
            "next_step": "Upload required documents",
            "required_documents": [
                "FSSAI_LICENSE", "PAN_CARD",
                "BANK_CANCELLED_CHEQUE",
                "OWNER_AADHAAR_FRONT",
                "OWNER_AADHAAR_BACK",
                "RESTAURANT_PHOTO_FRONT"
            ]
        }

    async def get_profile(self, user_id: uuid.UUID) -> dict:
        partner = await self._db.scalar(
            select(RestaurantPartner).where(RestaurantPartner.user_id == user_id)
        )
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")
        
        restaurant = await self._db.scalar(
            select(Restaurant).where(Restaurant.id == partner.restaurant_id)
        )
        timings_result = await self._db.scalars(
            select(RestaurantTiming).where(RestaurantTiming.restaurant_id == restaurant.id)
        )
        user = await self._db.scalar(
            select(User).where(User.id == user_id)
        )

        bank_last4 = f"****{partner.bank_account_number[-4:]}" if partner.bank_account_number else None

        return {
            "restaurant": {
                "id": restaurant.id,
                "name": restaurant.name,
                "slug": restaurant.slug,
                "cuisine_types": restaurant.cuisine_types,
                "city": restaurant.city,
                "full_address": restaurant.full_address,
                "latitude": restaurant.latitude,
                "longitude": restaurant.longitude,
                "phone": restaurant.phone,
                "image_url": restaurant.image_url,
                "cover_image_url": restaurant.cover_image_url,
                "rating": restaurant.rating,
                "total_reviews": restaurant.total_reviews,
                "avg_delivery_time": restaurant.avg_delivery_time,
                "min_order_amount": restaurant.min_order_amount,
                "delivery_fee": restaurant.delivery_fee,
                "is_open": restaurant.is_open,
                "is_pure_veg": restaurant.is_pure_veg,
                "has_offers": restaurant.has_offers
            },
            "partner": {
                "fe_id": None,
                "owner_name": partner.owner_name,
                "business_type": partner.business_type,
                "commission_rate": partner.commission_rate,
                "wallet_balance": partner.wallet_balance,
                "total_revenue": partner.total_revenue,
                "total_orders": partner.total_orders,
                "fssai_number": partner.fssai_number,
                "fssai_expiry": partner.fssai_expiry,
                "gstin": partner.gstin,
                "bank_account_number": bank_last4
            },
            "timings": [
                {
                    "day_of_week": t.day_of_week,
                    "opens_at": t.opens_at.strftime("%H:%M"),
                    "closes_at": t.closes_at.strftime("%H:%M"),
                    "is_closed": t.is_closed
                } for t in timings_result.all()
            ],
            "document_status": user.restaurant_status,
            "restaurant_status": user.restaurant_status
        }

    async def update_profile(self, user_id: uuid.UUID, data: dict) -> Restaurant:
        partner = await self._db.scalar(select(RestaurantPartner).where(RestaurantPartner.user_id == user_id))
        restaurant = await self._db.scalar(select(Restaurant).where(Restaurant.id == partner.restaurant_id))

        for key, value in data.items():
            if value is not None and hasattr(restaurant, key) and key not in ["city", "full_address"]:
                setattr(restaurant, key, value)
        
        await self._db.commit()
        await self._db.refresh(restaurant)
        return restaurant

    async def toggle_open_status(self, user_id: uuid.UUID, is_open: bool) -> dict:
        partner = await self._db.scalar(select(RestaurantPartner).where(RestaurantPartner.user_id == user_id))
        restaurant = await self._db.scalar(select(Restaurant).where(Restaurant.id == partner.restaurant_id))

        if not is_open:
            active_orders_count = await self._db.scalar(
                select(func.count()).select_from(Order).where(
                    Order.restaurant_id == restaurant.id,
                    Order.status.in_(["PLACED", "CONFIRMED", "PREPARING"])
                )
            )
            if active_orders_count and active_orders_count > 0:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error_code": "ACTIVE_ORDERS_EXIST",
                        "active_order_count": active_orders_count,
                        "message": "Complete active orders before closing"
                    }
                )

        restaurant.is_open = is_open
        await self._db.commit()
        return {"is_open": is_open, "message": "Restaurant status updated"}

    async def get_timings(self, user_id: uuid.UUID) -> list[dict]:
        partner = await self._db.scalar(select(RestaurantPartner).where(RestaurantPartner.user_id == user_id))
        timings = await self._db.scalars(select(RestaurantTiming).where(RestaurantTiming.restaurant_id == partner.restaurant_id))
        return [
            {
                "day_of_week": t.day_of_week,
                "opens_at": t.opens_at.strftime("%H:%M"),
                "closes_at": t.closes_at.strftime("%H:%M"),
                "is_closed": t.is_closed
            } for t in timings.all()
        ]

    async def update_timings(self, user_id: uuid.UUID, timings_data: list[dict]) -> list[dict]:
        partner = await self._db.scalar(select(RestaurantPartner).where(RestaurantPartner.user_id == user_id))
        for t_data in timings_data:
            timing = await self._db.scalar(
                select(RestaurantTiming).where(
                    RestaurantTiming.restaurant_id == partner.restaurant_id,
                    RestaurantTiming.day_of_week == t_data["day_of_week"]
                )
            )
            if timing:
                timing.opens_at = time.fromisoformat(t_data["opens_at"])
                timing.closes_at = time.fromisoformat(t_data["closes_at"])
                timing.is_closed = t_data["is_closed"]
        
        await self._db.commit()
        return await self.get_timings(user_id)
