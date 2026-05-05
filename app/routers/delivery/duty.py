"""
Duty toggle router — SPEC2.md Section 6.
Prefix: /api/v1/partner/duty
Requires KYC-approved partner.

Endpoints:
  POST /start  — go online, create shift
  POST /stop   — go offline, end shift with summary
  GET  /status  — current duty + shift + active assignment info
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from app.dependencies import ApprovedPartner, DB, Redis
from app.models.delivery_assignment import DeliveryAssignment, AssignmentStatus
from app.models.partner_earnings import PartnerEarnings
from app.models.partner_shift import PartnerShift
from app.models.order import Order
from app.models.restaurant import Restaurant
from app.services.assignment_service import AssignmentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/partner/duty", tags=["Partner Duty"])


class DutyStartRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


# ── POST /start ─────────────────────────────────────────────────────────────

@router.post("/start")
async def start_duty(
    body: DutyStartRequest,
    partner: ApprovedPartner,
    db: DB,
):
    """Go online — start a new shift."""
    if partner.is_online:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "ALREADY_ONLINE",
                "message": "You are already online",
            },
        )

    partner.is_online = True
    partner.current_latitude = body.latitude
    partner.current_longitude = body.longitude
    partner.last_location_at = datetime.now(UTC)

    shift = PartnerShift(
        partner_id=partner.id,
        city=partner.city or "",
    )
    db.add(shift)
    await db.flush()
    await db.refresh(shift)

    return {
        "status": "ONLINE",
        "shift_id": str(shift.id),
        "started_at": shift.started_at.isoformat() if shift.started_at else None,
        "message": "You are now online and can receive orders",
    }


# ── POST /stop ──────────────────────────────────────────────────────────────

@router.post("/stop")
async def stop_duty(
    partner: ApprovedPartner,
    db: DB,
):
    """Go offline — end active shift with summary."""
    if not partner.is_online:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "ALREADY_OFFLINE",
                "message": "You are already offline",
            },
        )

    # Check for active delivery
    active_statuses = [
        AssignmentStatus.ASSIGNED,
        AssignmentStatus.ACCEPTED,
        AssignmentStatus.PICKED_UP,
        AssignmentStatus.REACHED_RESTAURANT,
        AssignmentStatus.REACHED_CUSTOMER,
    ]
    active_assignment = await db.scalar(
        select(DeliveryAssignment).where(
            DeliveryAssignment.partner_id == partner.id,
            DeliveryAssignment.status.in_(active_statuses),
        )
    )
    if active_assignment:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "ACTIVE_DELIVERY_IN_PROGRESS",
                "message": "Cannot go offline during an active delivery",
                "assignment_id": str(active_assignment.id),
            },
        )

    partner.is_online = False

    # Find active shift
    active_shift = await db.scalar(
        select(PartnerShift).where(
            PartnerShift.partner_id == partner.id,
            PartnerShift.ended_at.is_(None),
        ).order_by(PartnerShift.started_at.desc())
    )

    shift_summary = {
        "duration_minutes": 0,
        "deliveries_completed": 0,
        "earnings": 0.0,
        "started_at": None,
        "ended_at": None,
    }

    if active_shift:
        now = datetime.now(UTC)
        active_shift.ended_at = now
        started = active_shift.started_at.replace(tzinfo=UTC) if active_shift.started_at.tzinfo is None else active_shift.started_at
        duration_minutes = int((now - started).total_seconds() / 60)
        active_shift.duration_minutes = duration_minutes

        # Compute shift earnings: SUM of total_earned for deliveries in this shift
        earnings_sum = await db.scalar(
            select(func.coalesce(func.sum(PartnerEarnings.total_earned), 0)).where(
                PartnerEarnings.partner_id == partner.id,
                PartnerEarnings.earned_at >= active_shift.started_at,
            )
        )
        active_shift.earnings_in_shift = float(earnings_sum or 0)

        shift_summary = {
            "duration_minutes": duration_minutes,
            "deliveries_completed": active_shift.deliveries_in_shift,
            "earnings": float(active_shift.earnings_in_shift),
            "started_at": active_shift.started_at.isoformat(),
            "ended_at": now.isoformat(),
        }

    await db.flush()

    return {
        "status": "OFFLINE",
        "shift_summary": shift_summary,
    }


# ── GET /status ─────────────────────────────────────────────────────────────

@router.get("/status")
async def duty_status(
    partner: ApprovedPartner,
    db: DB,
    redis: Redis,
):
    """Current duty status, shift info, and active assignment."""
    current_shift = None
    if partner.is_online:
        shift = await db.scalar(
            select(PartnerShift).where(
                PartnerShift.partner_id == partner.id,
                PartnerShift.ended_at.is_(None),
            ).order_by(PartnerShift.started_at.desc())
        )
        if shift:
            now = datetime.now(UTC)
            started = shift.started_at.replace(tzinfo=UTC) if shift.started_at.tzinfo is None else shift.started_at
            duration = int((now - started).total_seconds() / 60)

            # Earnings so far in this shift
            earnings_so_far = await db.scalar(
                select(func.coalesce(func.sum(PartnerEarnings.total_earned), 0)).where(
                    PartnerEarnings.partner_id == partner.id,
                    PartnerEarnings.earned_at >= shift.started_at,
                )
            )

            current_shift = {
                "shift_id": str(shift.id),
                "started_at": shift.started_at.isoformat(),
                "duration_minutes": duration,
                "deliveries_so_far": shift.deliveries_in_shift,
                "earnings_so_far": float(earnings_so_far or 0),
            }

    # Active assignment
    active_assignment = None
    active_statuses = [
        AssignmentStatus.ASSIGNED,
        AssignmentStatus.ACCEPTED,
        AssignmentStatus.REACHED_RESTAURANT,
        AssignmentStatus.PICKED_UP,
        AssignmentStatus.REACHED_CUSTOMER,
    ]
    assignment = await db.scalar(
        select(DeliveryAssignment).where(
            DeliveryAssignment.partner_id == partner.id,
            DeliveryAssignment.status.in_(active_statuses),
        )
    )
    if assignment:
        order = await db.scalar(select(Order).where(Order.id == assignment.order_id))
        restaurant = None
        if order:
            restaurant = await db.scalar(
                select(Restaurant).where(Restaurant.id == order.restaurant_id)
            )
        active_assignment = {
            "assignment_id": str(assignment.id),
            "status": assignment.status.value,
            "restaurant_name": restaurant.name if restaurant else None,
            "customer_address": assignment.customer_address,
        }

    return {
        "is_online": partner.is_online,
        "current_shift": current_shift,
        "active_assignment": active_assignment,
    }
