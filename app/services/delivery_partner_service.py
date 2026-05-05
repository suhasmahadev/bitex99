import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.delivery_partner import DeliveryPartner
from app.models.user import User
from app.schemas.delivery_partner import PartnerProfileUpdate, PartnerProfileResponse
from fastapi import HTTPException

class DeliveryPartnerService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_profile(self, partner_id: uuid.UUID) -> PartnerProfileResponse:
        partner = await self._db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
        user = await self._db.scalar(select(User).where(User.id == partner.user_id))
        
        return PartnerProfileResponse(
            fe_id=partner.fe_id,
            name=user.name,
            phone=user.phone,
            city=partner.city,
            vehicle_type=partner.vehicle_type,
            vehicle_number=partner.vehicle_number,
            vehicle_model=partner.vehicle_model,
            is_online=partner.is_online,
            rating=float(partner.rating),
            total_ratings=partner.total_ratings,
            joined_at=partner.joined_at,
            overall_kyc_status=user.partner_status
        )

    async def update_profile(self, partner_id: uuid.UUID, data: PartnerProfileUpdate) -> PartnerProfileResponse:
        partner = await self._db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
        user = await self._db.scalar(select(User).where(User.id == partner.user_id))
        
        if data.name is not None:
            user.name = data.name
        if data.vehicle_type is not None:
            partner.vehicle_type = data.vehicle_type
        if data.vehicle_number is not None:
            partner.vehicle_number = data.vehicle_number
        if data.vehicle_model is not None:
            partner.vehicle_model = data.vehicle_model
            
        await self._db.commit()
        return await self.get_profile(partner_id)
        
    async def get_stats(self, partner_id: uuid.UUID) -> dict:
        partner = await self._db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
        
        deliveries = partner.total_deliveries
        if deliveries < 100:
            level = "BRONZE"
        elif deliveries < 500:
            level = "SILVER"
        elif deliveries < 1000:
            level = "GOLD"
        else:
            level = "PLATINUM"
            
        return {
            "total_deliveries": deliveries,
            "completion_rate": float(partner.completion_rate),
            "acceptance_rate": float(partner.acceptance_rate),
            "rating": float(partner.rating),
            "level": level,
            "total_earnings": float(partner.total_earnings),
            "wallet_balance": float(partner.wallet_balance),
        }
