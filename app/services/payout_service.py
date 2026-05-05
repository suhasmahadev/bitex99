import uuid
import time
import asyncio
import logging
from datetime import UTC, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.delivery_partner import DeliveryPartner
from app.models.payout import Payout, PayoutStatus
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

async def get_pending_payout(partner_id: uuid.UUID, db: AsyncSession) -> dict:
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
    
    now_utc = datetime.now(UTC)
    days_ahead = 0 - now_utc.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_monday = (now_utc + timedelta(days=days_ahead)).date()
    
    return {
        "pending_amount": float(partner.wallet_balance or 0) if partner else 0.0,
        "next_payout_date": next_monday.isoformat(),
        "breakdown": {
            "delivery_earnings": 0.0,
            "incentive_earnings": 0.0,
            "tips": 0.0
        }
    }

async def request_payout(partner_id: uuid.UUID, amount: float, db: AsyncSession) -> dict:
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
    if not partner:
        raise ValueError("Partner not found")
        
    wallet_bal = float(partner.wallet_balance or 0)
    if wallet_bal < amount:
        return {"error": "Insufficient balance", "error_code": "INSUFFICIENT_BALANCE", "status_code": 402}
        
    if amount < 50:
        return {"error": "Minimum withdrawal is 50", "error_code": "MIN_WITHDRAWAL_50", "status_code": 400}
        
    partner.wallet_balance = wallet_bal - amount
    
    now_utc = datetime.now(UTC)
    this_monday = (now_utc - timedelta(days=now_utc.weekday())).date()
    last_sunday = this_monday - timedelta(days=1)
    
    payout = Payout(
        partner_id=partner_id,
        amount=amount,
        payout_period_start=this_monday,
        payout_period_end=last_sunday,
        status=PayoutStatus.PROCESSING,
        bank_account="1234",
        initiated_at=datetime.now(UTC)
    )
    db.add(payout)
    await db.flush()
    payout_id = payout.id
    
    utr_number = f"BTXPAY{int(time.time())}"
    
    asyncio.create_task(simulate_processing(payout_id, utr_number))
    
    return {
        "amount": amount,
        "utr_number": utr_number,
        "message": f"₹{amount} transferred",
        "expected_time": "Within 2 hours"
    }
    
async def simulate_processing(payout_id: uuid.UUID, utr_number: str):
    await asyncio.sleep(2)
    async with AsyncSessionLocal() as db:
        payout = await db.scalar(select(Payout).where(Payout.id == payout_id))
        if payout:
            payout.status = PayoutStatus.PAID
            payout.utr_number = utr_number
            payout.paid_at = datetime.now(UTC)
            await db.commit()
