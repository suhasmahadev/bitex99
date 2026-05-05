import uuid
import logging
from datetime import UTC, datetime, date
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.delivery_partner import DeliveryPartner
from app.models.partner_earnings import PartnerEarnings
from app.models.incentive_rule import IncentiveRule
from app.models.partner_incentive import PartnerIncentive

logger = logging.getLogger(__name__)

async def check_and_award(
    partner_id: uuid.UUID,
    db: AsyncSession,
    redis
) -> None:
    now_utc = datetime.now(UTC)
    today = now_utc.date()
    
    today_count_query = select(func.count()).where(
        PartnerEarnings.partner_id == partner_id,
        func.date(PartnerEarnings.earned_at) == today
    )
    today_count = await db.scalar(today_count_query) or 0
    
    rules_query = select(IncentiveRule).where(
        IncentiveRule.is_active == True,
        or_(IncentiveRule.valid_from.is_(None), IncentiveRule.valid_from <= now_utc),
        or_(IncentiveRule.valid_until.is_(None), IncentiveRule.valid_until >= now_utc)
    )
    rules = (await db.execute(rules_query)).scalars().all()
    
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
    if not partner:
        return
        
    for rule in rules:
        awarded_query = select(PartnerIncentive).where(
            PartnerIncentive.partner_id == partner_id,
            PartnerIncentive.rule_id == rule.id,
            func.date(PartnerIncentive.earned_at) == today
        )
        already_awarded = await db.scalar(awarded_query)
        if already_awarded:
            continue
            
        should_award = False
        
        if rule.type.name == 'DAILY_ORDERS':
            if today_count >= (rule.threshold_value or 0):
                should_award = True
                
        elif rule.type.name == 'PEAK_HOUR':
            peak_count_query = select(func.count()).where(
                PartnerEarnings.partner_id == partner_id,
                func.date(PartnerEarnings.earned_at) == today,
                or_(
                    and_(func.extract('hour', PartnerEarnings.earned_at) >= 12, func.extract('hour', PartnerEarnings.earned_at) < 14),
                    and_(func.extract('hour', PartnerEarnings.earned_at) >= 19, func.extract('hour', PartnerEarnings.earned_at) < 22)
                )
            )
            peak_count = await db.scalar(peak_count_query) or 0
            if peak_count >= (rule.threshold_value or 0):
                should_award = True
                
        elif rule.type.name == 'ACCEPTANCE_RATE':
            if float(partner.acceptance_rate or 0) >= (rule.threshold_value or 0):
                should_award = True
                
        if should_award:
            await award_incentive(partner_id, rule, db)

async def award_incentive(partner_id: uuid.UUID, rule: IncentiveRule, db: AsyncSession):
    incentive = PartnerIncentive(
        partner_id=partner_id,
        rule_id=rule.id,
        bonus_amount=rule.bonus_amount,
        reason=rule.name,
        earned_at=datetime.now(UTC)
    )
    db.add(incentive)
    
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
    if partner:
        partner.wallet_balance = float(partner.wallet_balance or 0) + float(rule.bonus_amount)
    
    await db.flush()

async def get_active_incentives_with_progress(partner_id: uuid.UUID, db: AsyncSession) -> list:
    now_utc = datetime.now(UTC)
    today = now_utc.date()
    
    rules_query = select(IncentiveRule).where(
        IncentiveRule.is_active == True,
        or_(IncentiveRule.valid_from.is_(None), IncentiveRule.valid_from <= now_utc),
        or_(IncentiveRule.valid_until.is_(None), IncentiveRule.valid_until >= now_utc)
    )
    rules = (await db.execute(rules_query)).scalars().all()
    
    today_count = await db.scalar(select(func.count()).where(
        PartnerEarnings.partner_id == partner_id,
        func.date(PartnerEarnings.earned_at) == today
    )) or 0
    
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
    acc_rate = float(partner.acceptance_rate or 0) if partner else 0.0
    
    results = []
    for rule in rules:
        progress = 0
        if rule.type.name == 'DAILY_ORDERS':
            progress = today_count
        elif rule.type.name == 'ACCEPTANCE_RATE':
            progress = acc_rate
        elif rule.type.name == 'PEAK_HOUR':
            peak_count_query = select(func.count()).where(
                PartnerEarnings.partner_id == partner_id,
                func.date(PartnerEarnings.earned_at) == today,
                or_(
                    and_(func.extract('hour', PartnerEarnings.earned_at) >= 12, func.extract('hour', PartnerEarnings.earned_at) < 14),
                    and_(func.extract('hour', PartnerEarnings.earned_at) >= 19, func.extract('hour', PartnerEarnings.earned_at) < 22)
                )
            )
            progress = await db.scalar(peak_count_query) or 0
            
        threshold = float(rule.threshold_value or 1)
        remaining = max(0, threshold - progress)
        pct = min(100.0, (progress / threshold) * 100) if threshold > 0 else 100.0
        
        results.append({
            "name": rule.name,
            "bonus_amount": float(rule.bonus_amount),
            "progress": progress,
            "threshold": threshold,
            "remaining": remaining,
            "progress_percent": round(pct, 1),
            "description": f"Complete {remaining} more to earn ₹{rule.bonus_amount}"
        })
        
    return results
