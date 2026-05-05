import asyncio
import time
import uuid
from datetime import date, datetime, time as dt_time, timedelta, timezone

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except ImportError:  # pragma: no cover
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.order import Order, OrderStatus
from app.models.restaurant_partner import RestaurantPartner
from app.models.restaurant_payout import RestaurantPayout, PayoutStatus


def get_next_monday() -> date:
    today = date.today()
    days = (0 - today.weekday()) % 7
    if days == 0:
        days = 7
    return today + timedelta(days=days)


def _ist_monday_start() -> datetime:
    today = datetime.now(IST).date()
    monday = today - timedelta(days=today.weekday())
    naive = datetime.combine(monday, dt_time.min)
    if hasattr(IST, "localize"):
        return IST.localize(naive).astimezone(timezone.utc)
    return naive.replace(tzinfo=IST).astimezone(timezone.utc)


async def _mark_paid_later(payout_id: uuid.UUID) -> None:
    await asyncio.sleep(2)
    async with AsyncSessionLocal() as db:
        payout = await db.scalar(select(RestaurantPayout).where(RestaurantPayout.id == payout_id))
        if payout and payout.status == PayoutStatus.PROCESSING:
            payout.status = PayoutStatus.PAID
            payout.utr_number = f"BTXRST{int(time.time())}"
            payout.paid_at = datetime.now(timezone.utc)
            await db.commit()


class RestaurantPayoutService:
    async def get_pending_payout(self, partner_id: uuid.UUID, db: AsyncSession) -> dict:
        partner = await db.scalar(select(RestaurantPartner).where(RestaurantPartner.id == partner_id))
        if not partner:
            raise HTTPException(status_code=404, detail="Restaurant partner not found")

        week_start = _ist_monday_start()
        row = (
            await db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(total_amount), 0) AS gross,
                           COUNT(id) AS orders
                    FROM orders
                    WHERE restaurant_id = :restaurant_id
                    AND status = 'DELIVERED'
                    AND delivered_at >= :week_start
                    """
                ),
                {"restaurant_id": partner.restaurant_id, "week_start": week_start},
            )
        ).mappings().one()
        gross = float(row["gross"] or 0)
        orders = int(row["orders"] or 0)
        rate = float(partner.commission_rate or 20)
        commission = round(gross * rate / 100, 2)
        net = round(gross - commission, 2)

        daily_rows = (
            await db.execute(
                text(
                    """
                    SELECT DATE(delivered_at AT TIME ZONE 'Asia/Kolkata') AS day,
                           COUNT(*) AS orders,
                           COALESCE(SUM(total_amount), 0) AS gross
                    FROM orders
                    WHERE restaurant_id = :restaurant_id
                    AND status = 'DELIVERED'
                    AND delivered_at >= :week_start
                    GROUP BY DATE(delivered_at AT TIME ZONE 'Asia/Kolkata')
                    ORDER BY day ASC
                    """
                ),
                {"restaurant_id": partner.restaurant_id, "week_start": week_start},
            )
        ).mappings().all()
        breakdown = []
        for day in daily_rows:
            day_gross = float(day["gross"] or 0)
            day_commission = round(day_gross * rate / 100, 2)
            breakdown.append({
                "date": str(day["day"]),
                "orders": int(day["orders"] or 0),
                "gross": day_gross,
                "commission": day_commission,
                "net": round(day_gross - day_commission, 2),
            })

        return {
            "pending_amount": float(partner.wallet_balance or 0),
            "pending_orders": orders,
            "gross_revenue": gross,
            "commission_deducted": commission,
            "net_payout": net,
            "next_payout_date": get_next_monday().isoformat(),
            "breakdown_by_day": breakdown,
        }

    async def request_payout(self, partner_id: uuid.UUID, amount: float, db: AsyncSession) -> dict:
        partner = await db.scalar(select(RestaurantPartner).where(RestaurantPartner.id == partner_id))
        if not partner:
            raise HTTPException(status_code=404, detail="Restaurant partner not found")
        if amount < 100:
            raise HTTPException(status_code=400, detail={"error_code": "MIN_WITHDRAWAL", "minimum": 100})
        if amount > float(partner.wallet_balance or 0):
            raise HTTPException(
                status_code=402,
                detail={
                    "error_code": "INSUFFICIENT_BALANCE",
                    "available": float(partner.wallet_balance or 0),
                    "requested": amount,
                },
            )

        today = date.today()
        last_monday = today - timedelta(days=today.weekday())
        yesterday = today - timedelta(days=1)
        rate = float(partner.commission_rate or 20)
        gross = round(amount / (1 - rate / 100), 2) if rate < 100 else amount
        commission = round(gross * rate / 100, 2)
        order_count = await db.scalar(
            select(func.count(Order.id)).where(
                Order.restaurant_id == partner.restaurant_id,
                Order.status == OrderStatus.DELIVERED,
                Order.delivered_at >= _ist_monday_start(),
            )
        ) or 0
        utr = f"BTXRST{int(time.time())}"
        bank_last4 = partner.bank_account_number[-4:] if partner.bank_account_number else None
        payout = RestaurantPayout(
            partner_id=partner.id,
            period_start=last_monday,
            period_end=yesterday,
            gross_revenue=gross,
            commission_deducted=commission,
            net_payout=amount,
            order_count=order_count,
            status=PayoutStatus.PROCESSING,
            bank_account=bank_last4,
            utr_number=utr,
        )
        db.add(payout)
        partner.wallet_balance = float(partner.wallet_balance or 0) - amount
        await db.flush()
        asyncio.create_task(_mark_paid_later(payout.id))
        return {
            "amount": amount,
            "utr_number": utr,
            "message": f"Rs {amount:.2f} initiated to bank account",
            "expected_time": "Within 4 hours",
        }

    async def get_payout_history(self, partner_id: uuid.UUID, db: AsyncSession, page: int, limit: int) -> dict:
        total = await db.scalar(
            select(func.count(RestaurantPayout.id)).where(RestaurantPayout.partner_id == partner_id)
        ) or 0
        payouts = await db.scalars(
            select(RestaurantPayout)
            .where(RestaurantPayout.partner_id == partner_id)
            .order_by(RestaurantPayout.initiated_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        items = [
            {
                "id": str(p.id),
                "amount": float(p.net_payout),
                "gross_revenue": float(p.gross_revenue),
                "commission_deducted": float(p.commission_deducted),
                "order_count": p.order_count,
                "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                "bank_account": p.bank_account,
                "utr_number": p.utr_number,
                "period_start": p.period_start.isoformat(),
                "period_end": p.period_end.isoformat(),
                "initiated_at": p.initiated_at.isoformat() if p.initiated_at else None,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            }
            for p in payouts.all()
        ]
        return {"items": items, "total": total, "page": page, "limit": limit}
