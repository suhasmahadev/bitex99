import uuid
from datetime import UTC, datetime, time, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.delivery_partner import DeliveryPartner
from app.models.delivery_assignment import DeliveryAssignment
from app.models.partner_earnings import PartnerEarnings
from app.models.partner_shift import PartnerShift
from app.utils.surge_detector import get_surge_pay

async def calculate_earnings(
    partner_id: uuid.UUID,
    assignment_id: uuid.UUID,
    distance_km: float,
    city: str,
    redis,
    db: AsyncSession
) -> PartnerEarnings:
    base_pay = 25.00
    distance_pay = round(max(0, (distance_km - 3.0) * 8.0), 2)
    surge_pay = await get_surge_pay(city, redis)
    total = round(base_pay + distance_pay + surge_pay, 2)
    
    assignment = await db.scalar(select(DeliveryAssignment).where(DeliveryAssignment.id == assignment_id))
    
    earnings = PartnerEarnings(
        partner_id=partner_id,
        assignment_id=assignment_id,
        order_id=assignment.order_id if assignment else None,
        base_pay=base_pay,
        distance_pay=distance_pay,
        surge_pay=surge_pay,
        tip_amount=0,
        total_earned=total,
        earned_at=datetime.now(UTC)
    )
    db.add(earnings)
    
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
    if partner:
        partner.total_deliveries = (partner.total_deliveries or 0) + 1
        partner.total_earnings = float(partner.total_earnings or 0) + total
        partner.wallet_balance = float(partner.wallet_balance or 0) + total
        
    active_shift = await db.scalar(
        select(PartnerShift).where(
            PartnerShift.partner_id == partner_id,
            PartnerShift.ended_at.is_(None)
        ).order_by(PartnerShift.started_at.desc())
    )
    if active_shift:
        active_shift.deliveries_in_shift = (active_shift.deliveries_in_shift or 0) + 1
        active_shift.earnings_in_shift = float(active_shift.earnings_in_shift or 0) + total
        
    await db.flush()
    return earnings

async def get_today_earnings(partner_id: uuid.UUID, db: AsyncSession) -> dict:
    now_utc = datetime.now(UTC)
    date_start = datetime.combine(now_utc.date(), time.min).replace(tzinfo=UTC)
    date_end = datetime.combine(now_utc.date(), time.max).replace(tzinfo=UTC)
    
    query = select(
        func.sum(PartnerEarnings.base_pay).label('base_pay'),
        func.sum(PartnerEarnings.distance_pay).label('distance_pay'),
        func.sum(PartnerEarnings.surge_pay).label('surge_pay'),
        func.sum(PartnerEarnings.tip_amount).label('tips'),
        func.sum(PartnerEarnings.total_earned).label('total_earned'),
        func.count().label('deliveries_completed')
    ).where(
        PartnerEarnings.partner_id == partner_id,
        PartnerEarnings.earned_at >= date_start,
        PartnerEarnings.earned_at <= date_end
    )
    
    result = await db.execute(query)
    row = result.first()
    
    shift_hours = 0.0
    shift_seconds = await db.scalar(
        select(
            func.coalesce(
                func.sum(
                    func.extract(
                        "epoch",
                        func.coalesce(PartnerShift.ended_at, now_utc) - PartnerShift.started_at,
                    )
                ),
                0,
            )
        ).where(
            PartnerShift.partner_id == partner_id,
            PartnerShift.started_at >= date_start,
        )
    )
    shift_hours = float(shift_seconds or 0) / 3600
        
    deliveries = row.deliveries_completed or 0
    total = float(row.total_earned or 0)
    avg_per_delivery = total / deliveries if deliveries > 0 else 0.0
    
    return {
        "date": now_utc.date().isoformat(),
        "total_earned": total,
        "deliveries_completed": deliveries,
        "breakdown": {
            "base_pay": float(row.base_pay or 0),
            "distance_pay": float(row.distance_pay or 0),
            "surge_pay": float(row.surge_pay or 0),
            "tips": float(row.tips or 0),
            "incentives": 0.0
        },
        "shift_hours": round(shift_hours, 1),
        "avg_per_delivery": round(avg_per_delivery, 2)
    }

async def get_weekly_earnings(partner_id: uuid.UUID, db: AsyncSession):
    now_utc = datetime.now(UTC)
    start_date = (now_utc - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = select(
        func.date(PartnerEarnings.earned_at).label('dt'),
        func.sum(PartnerEarnings.total_earned).label('total'),
        func.count().label('orders')
    ).where(
        PartnerEarnings.partner_id == partner_id,
        PartnerEarnings.earned_at >= start_date
    ).group_by(func.date(PartnerEarnings.earned_at))
    
    result = await db.execute(query)
    
    chart_data = []
    daily_map = {row.dt: {"orders": row.orders, "total": float(row.total)} for row in result.all()}
    
    total_week = 0.0
    for i in range(7):
        d = (start_date + timedelta(days=i)).date()
        stats = daily_map.get(d, {"orders": 0, "total": 0.0})
        total_week += stats["total"]
        chart_data.append({
            "date": d.isoformat(),
            "orders": stats["orders"],
            "amount": stats["total"]
        })
        
    return {
        "weekly_total": total_week,
        "chart_data": chart_data
    }
