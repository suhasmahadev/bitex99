"""
Assignment service — SPEC2.md Sections 7 & 8.

Core logistics: auto-assign nearest partner, handle acceptance timeout,
manage the full delivery lifecycle (accept → deliver/fail).
Background tasks use their OWN database sessions to avoid stale state.
"""

import asyncio
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.database import AsyncSessionLocal
from app.models.delivery_assignment import DeliveryAssignment, AssignmentStatus
from app.models.delivery_otp import DeliveryOtp
from app.models.delivery_partner import DeliveryPartner
from app.models.order import Order, OrderStatus
from app.models.partner_earnings import PartnerEarnings
from app.models.partner_shift import PartnerShift
from app.models.restaurant import Restaurant
from app.models.restaurant_partner import RestaurantPartner
from app.models.user import User
from app.utils.assignment_engine import find_nearest_partners, PartnerWithDistance
from app.utils.surge_detector import get_surge_pay

logger = logging.getLogger(__name__)


def mask_phone(phone: str) -> str:
    """Mask phone: show only last 4 digits. +91XXXXXX5678"""
    if len(phone) <= 4:
        return phone
    return "+91XXXXXX" + phone[-4:]


class AssignmentService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self._db = db
        self._redis = redis

    # ══════════════════════════════════════════════════════════════════════════
    # AUTO-ASSIGN — called after order is placed/confirmed
    # ══════════════════════════════════════════════════════════════════════════

    async def auto_assign_partner(self, order_id: uuid.UUID) -> DeliveryAssignment | None:
        """
        Find nearest available partner and assign the order.
        Uses its own DB session so it can run as a background task.
        """
        async with AsyncSessionLocal() as db:
            try:
                return await self._do_assign(order_id, db)
            except Exception as e:
                logger.exception("auto_assign_partner failed for order %s: %s", order_id, e)
                return None

    async def _do_assign(self, order_id: uuid.UUID, db: AsyncSession) -> DeliveryAssignment | None:
        # Step 1: Fetch order
        order = await db.scalar(select(Order).where(Order.id == order_id))
        if not order:
            logger.error("Order %s not found for assignment", order_id)
            return None

        # Check if assignment already exists
        existing = await db.scalar(
            select(DeliveryAssignment).where(DeliveryAssignment.order_id == order_id)
        )
        if existing and existing.status not in (AssignmentStatus.REJECTED, AssignmentStatus.TIMED_OUT, AssignmentStatus.FAILED):
            logger.info("Order %s already has active assignment %s", order_id, existing.id)
            return existing

        # Step 2: Fetch restaurant
        restaurant = await db.scalar(select(Restaurant).where(Restaurant.id == order.restaurant_id))
        if not restaurant:
            logger.error("Restaurant not found for order %s", order_id)
            return None

        rest_lat = float(restaurant.latitude) if restaurant.latitude else 0.0
        rest_lng = float(restaurant.longitude) if restaurant.longitude else 0.0

        # Step 3: Find nearest partners
        partners = await find_nearest_partners(
            restaurant_lat=rest_lat,
            restaurant_lng=rest_lng,
            city=restaurant.city,
            db=db,
            limit=5,
        )

        # Step 4: No partners available
        if not partners:
            await self._redis.setex(f"unassigned:{order_id}", 600, "1")
            logger.warning("No partners available for order %s in %s", order_id, restaurant.city)
            return None

        # Step 5: Assign to nearest
        nearest = partners[0]
        remaining = partners[1:]

        # Step 6: Generate delivery OTP
        otp_code = str(secrets.randbelow(9000) + 1000)

        # Step 7: Snapshot customer info
        addr_snapshot = order.delivery_address_snapshot or {}
        user = await db.scalar(select(User).where(User.id == order.user_id))

        # Step 8: Create assignment
        assignment = DeliveryAssignment(
            order_id=order_id,
            partner_id=nearest.id,
            status=AssignmentStatus.ASSIGNED,
            distance_km=nearest.distance_km,
            restaurant_latitude=rest_lat,
            restaurant_longitude=rest_lng,
            customer_latitude=addr_snapshot.get("latitude"),
            customer_longitude=addr_snapshot.get("longitude"),
            customer_address=addr_snapshot.get("full_address", ""),
            customer_name=user.name if user else None,
            customer_phone=mask_phone(user.phone) if user else None,
        )
        db.add(assignment)
        await db.flush()

        # Step 9: Create delivery OTP
        delivery_otp = DeliveryOtp(
            assignment_id=assignment.id,
            otp=otp_code,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        db.add(delivery_otp)

        await db.commit()
        await db.refresh(assignment)

        # Step 10: Store pending key in Redis (45s TTL)
        await self._redis.setex(
            f"assignment_pending:{nearest.id}",
            45,
            str(assignment.id),
        )

        # Remove unassigned key if it exists
        await self._redis.delete(f"unassigned:{order_id}")

        logger.info(
            "Order %s assigned to partner %s (fe_id=%s, distance=%.2f km, OTP=%s)",
            order_id, nearest.id, nearest.fe_id, nearest.distance_km, otp_code,
        )

        # Step 12: Schedule timeout handler
        asyncio.create_task(
            self._handle_timeout(assignment.id, nearest.id, order_id, remaining)
        )

        return assignment

    async def _handle_timeout(
        self,
        assignment_id: uuid.UUID,
        partner_id: uuid.UUID,
        order_id: uuid.UUID,
        remaining_partners: list[PartnerWithDistance],
    ) -> None:
        """After 45 seconds, time out the assignment if not accepted."""
        await asyncio.sleep(45)

        async with AsyncSessionLocal() as db:
            try:
                assignment = await db.scalar(
                    select(DeliveryAssignment).where(DeliveryAssignment.id == assignment_id)
                )
                if not assignment or assignment.status != AssignmentStatus.ASSIGNED:
                    return  # Already accepted/rejected

                assignment.status = AssignmentStatus.TIMED_OUT
                logger.info(
                    "Assignment %s timed out for partner %s", assignment_id, partner_id
                )

                # Decrement acceptance rate
                partner = await db.scalar(
                    select(DeliveryPartner).where(DeliveryPartner.id == partner_id)
                )
                if partner:
                    total = partner.total_deliveries + 1
                    new_rate = max(0, ((float(partner.acceptance_rate) * total) - 100) / total)
                    partner.acceptance_rate = round(new_rate, 2)

                await db.commit()

                # Try next partner
                if remaining_partners:
                    logger.info("Reassigning order %s to next partner", order_id)
                    await self._assign_next(order_id, remaining_partners, db)
                else:
                    logger.warning("No more partners for order %s — marking failed", order_id)
            except Exception as e:
                logger.exception("Timeout handler failed: %s", e)

    async def _assign_next(
        self,
        order_id: uuid.UUID,
        partners: list[PartnerWithDistance],
        db: AsyncSession,
    ) -> None:
        """Assign to the next partner in queue."""
        # Use a fresh assignment via auto_assign
        await self.auto_assign_partner(order_id)

    # ══════════════════════════════════════════════════════════════════════════
    # ACCEPT
    # ══════════════════════════════════════════════════════════════════════════

    async def accept_assignment(
        self, assignment_id: uuid.UUID, partner: DeliveryPartner
    ) -> dict:
        assignment = await self._db.scalar(
            select(DeliveryAssignment)
            .options(
                selectinload(DeliveryAssignment.delivery_otp),
                joinedload(DeliveryAssignment.order).joinedload(Order.restaurant),
            )
            .where(DeliveryAssignment.id == assignment_id)
        )
        if not assignment:
            return {"error": "Assignment not found", "status_code": 404}

        if assignment.partner_id != partner.id:
            return {"error": "This assignment does not belong to you", "status_code": 403}

        if assignment.status != AssignmentStatus.ASSIGNED:
            return {
                "error": "Assignment is no longer available",
                "error_code": "INVALID_ASSIGNMENT_STATUS",
                "status_code": 409,
            }

        # Check Redis pending key
        pending = await self._redis.get(f"assignment_pending:{partner.id}")
        if not pending:
            return {
                "error": "Assignment window has expired (45 seconds)",
                "error_code": "ASSIGNMENT_EXPIRED",
                "status_code": 409,
            }

        # Accept
        assignment.status = AssignmentStatus.ACCEPTED
        assignment.accepted_at = datetime.now(UTC)

        # Delete Redis key
        await self._redis.delete(f"assignment_pending:{partner.id}")

        otp_record = assignment.delivery_otp
        order = assignment.order
        restaurant = order.restaurant if order else None

        await self._db.flush()

        # Build waypoints
        waypoints = [
            {
                "step": 1,
                "type": "PICKUP",
                "label": restaurant.name if restaurant else "Restaurant",
                "address": restaurant.full_address if restaurant else "",
                "latitude": float(assignment.restaurant_latitude) if assignment.restaurant_latitude else None,
                "longitude": float(assignment.restaurant_longitude) if assignment.restaurant_longitude else None,
                "instructions": "Show this order ID at counter",
            },
            {
                "step": 2,
                "type": "DELIVERY",
                "label": f"Customer: {assignment.customer_name or 'Customer'}",
                "address": assignment.customer_address or "",
                "latitude": float(assignment.customer_latitude) if assignment.customer_latitude else None,
                "longitude": float(assignment.customer_longitude) if assignment.customer_longitude else None,
                "instructions": "Call customer if door is closed",
                "delivery_otp": otp_record.otp if otp_record else None,
            },
        ]

        return {
            "assignment_id": str(assignment.id),
            "status": "ACCEPTED",
            "waypoints": waypoints,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # REJECT
    # ══════════════════════════════════════════════════════════════════════════

    async def reject_assignment(
        self, assignment_id: uuid.UUID, partner: DeliveryPartner, reason: str | None = None
    ) -> dict:
        assignment = await self._db.scalar(
            select(DeliveryAssignment).where(DeliveryAssignment.id == assignment_id)
        )
        if not assignment:
            return {"error": "Assignment not found", "status_code": 404}
        if assignment.partner_id != partner.id:
            return {"error": "This assignment does not belong to you", "status_code": 403}
        if assignment.status != AssignmentStatus.ASSIGNED:
            return {"error": "Assignment is no longer available", "status_code": 409}

        assignment.status = AssignmentStatus.REJECTED
        assignment.rejection_reason = reason
        assignment.rejected_at = datetime.now(UTC)

        # Delete Redis key
        await self._redis.delete(f"assignment_pending:{partner.id}")

        # Decrement acceptance rate
        total = partner.total_deliveries + 1
        new_rate = max(0, ((float(partner.acceptance_rate) * total) - 100) / total)
        partner.acceptance_rate = round(new_rate, 2)

        await self._db.flush()

        # Trigger reassignment in background
        asyncio.create_task(self.auto_assign_partner(assignment.order_id))

        return {"message": "Order rejected"}

    # ══════════════════════════════════════════════════════════════════════════
    # REACHED RESTAURANT
    # ══════════════════════════════════════════════════════════════════════════

    async def reached_restaurant(
        self, assignment_id: uuid.UUID, partner: DeliveryPartner
    ) -> dict:
        assignment = await self._db.scalar(
            select(DeliveryAssignment).where(DeliveryAssignment.id == assignment_id)
        )
        if not assignment:
            return {"error": "Assignment not found", "status_code": 404}
        if assignment.partner_id != partner.id:
            return {"error": "Forbidden", "status_code": 403}
        if assignment.status != AssignmentStatus.ACCEPTED:
            return {"error": "Must be ACCEPTED first", "status_code": 409}

        assignment.status = AssignmentStatus.REACHED_RESTAURANT
        await self._db.flush()

        return {"status": "REACHED_RESTAURANT"}

    # ══════════════════════════════════════════════════════════════════════════
    # PICKED UP
    # ══════════════════════════════════════════════════════════════════════════

    async def picked_up(
        self, assignment_id: uuid.UUID, partner: DeliveryPartner
    ) -> dict:
        assignment = await self._db.scalar(
            select(DeliveryAssignment).where(DeliveryAssignment.id == assignment_id)
        )
        if not assignment:
            return {"error": "Assignment not found", "status_code": 404}
        if assignment.partner_id != partner.id:
            return {"error": "Forbidden", "status_code": 403}
        if assignment.status not in (AssignmentStatus.ACCEPTED, AssignmentStatus.REACHED_RESTAURANT):
            return {"error": "Invalid status for pickup", "status_code": 409}

        assignment.status = AssignmentStatus.PICKED_UP
        assignment.picked_up_at = datetime.now(UTC)

        # Update order status to OUT_FOR_DELIVERY
        order = await self._db.scalar(select(Order).where(Order.id == assignment.order_id))
        if order:
            order.status = OrderStatus.OUT_FOR_DELIVERY

        await self._db.flush()

        return {
            "status": "PICKED_UP",
            "estimated_delivery_minutes": int(float(assignment.distance_km or 2) * 4),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # REACHED CUSTOMER
    # ══════════════════════════════════════════════════════════════════════════

    async def reached_customer(
        self, assignment_id: uuid.UUID, partner: DeliveryPartner
    ) -> dict:
        assignment = await self._db.scalar(
            select(DeliveryAssignment).where(DeliveryAssignment.id == assignment_id)
        )
        if not assignment:
            return {"error": "Assignment not found", "status_code": 404}
        if assignment.partner_id != partner.id:
            return {"error": "Forbidden", "status_code": 403}
        if assignment.status != AssignmentStatus.PICKED_UP:
            return {"error": "Must be PICKED_UP first", "status_code": 409}

        assignment.status = AssignmentStatus.REACHED_CUSTOMER
        await self._db.flush()

        return {
            "status": "REACHED_CUSTOMER",
            "instruction": "Ask customer for 4-digit OTP",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # DELIVER (OTP verification)
    # ══════════════════════════════════════════════════════════════════════════

    async def deliver(
        self, assignment_id: uuid.UUID, partner: DeliveryPartner, otp: str
    ) -> dict:
        assignment = await self._db.scalar(
            select(DeliveryAssignment).where(DeliveryAssignment.id == assignment_id)
        )
        if not assignment:
            return {"error": "Assignment not found", "status_code": 404}
        if assignment.partner_id != partner.id:
            return {"error": "Forbidden", "status_code": 403}
        if assignment.status not in (AssignmentStatus.PICKED_UP, AssignmentStatus.REACHED_CUSTOMER):
            return {"error": "Invalid status for delivery", "status_code": 409}

        # Fetch OTP by ASSIGNMENT_ID (not order_id)
        otp_record = await self._db.scalar(
            select(DeliveryOtp).where(DeliveryOtp.assignment_id == assignment_id)
        )
        if not otp_record:
            return {"error": "Delivery OTP not found", "status_code": 404}

        if otp_record.is_used:
            return {"error_code": "OTP_ALREADY_USED", "error": "OTP already used", "status_code": 409}

        if otp_record.expires_at and datetime.now(UTC) > otp_record.expires_at.replace(tzinfo=UTC):
            return {
                "error_code": "OTP_EXPIRED",
                "error": "Delivery OTP has expired. Contact support.",
                "status_code": 409,
            }

        if otp != otp_record.otp:
            return {
                "error_code": "INVALID_DELIVERY_OTP",
                "error": "Incorrect OTP. Please ask customer again.",
                "status_code": 401,
            }

        # Mark OTP used
        otp_record.is_used = True

        # Update assignment
        assignment.status = AssignmentStatus.DELIVERED
        assignment.delivered_at = datetime.now(UTC)

        # Update order
        order = await self._db.scalar(select(Order).where(Order.id == assignment.order_id))
        if order:
            order.status = OrderStatus.DELIVERED
            order.delivered_at = datetime.now(UTC)
            restaurant_partner = await self._db.scalar(
                select(RestaurantPartner).where(RestaurantPartner.restaurant_id == order.restaurant_id)
            )
            if restaurant_partner:
                commission_rate = float(restaurant_partner.commission_rate or 20)
                gross = float(order.total_amount or 0)
                commission = gross * (commission_rate / 100)
                net = gross - commission
                restaurant_partner.wallet_balance = float(restaurant_partner.wallet_balance or 0) + net
                restaurant_partner.total_revenue = float(restaurant_partner.total_revenue or 0) + gross
                restaurant_partner.total_orders = int(restaurant_partner.total_orders or 0) + 1

        from app.services.earnings_service import calculate_earnings
        from app.services.incentive_service import check_and_award
        
        distance_km = float(assignment.distance_km) if assignment.distance_km else 0.0
        earnings = await calculate_earnings(
            partner_id=partner.id,
            assignment_id=assignment.id,
            distance_km=distance_km,
            city=partner.city or "",
            redis=self._redis,
            db=self._db
        )
        
        await check_and_award(partner.id, self._db, self._redis)

        return {
            "status": "DELIVERED",
            "earnings": {
                "base_pay": float(earnings.base_pay),
                "distance_pay": float(earnings.distance_pay),
                "surge_pay": float(earnings.surge_pay),
                "total_earned": float(earnings.total_earned),
            },
            "wallet_balance": float(partner.wallet_balance or 0),
            "message": f"Great job! ₹{float(earnings.total_earned):.2f} added to your wallet",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # FAILED
    # ══════════════════════════════════════════════════════════════════════════

    async def fail_delivery(
        self, assignment_id: uuid.UUID, partner: DeliveryPartner,
        reason: str, description: str = ""
    ) -> dict:
        assignment = await self._db.scalar(
            select(DeliveryAssignment).where(DeliveryAssignment.id == assignment_id)
        )
        if not assignment:
            return {"error": "Assignment not found", "status_code": 404}
        if assignment.partner_id != partner.id:
            return {"error": "Forbidden", "status_code": 403}
        if assignment.status not in (AssignmentStatus.PICKED_UP, AssignmentStatus.REACHED_CUSTOMER):
            return {"error": "Invalid status for failure", "status_code": 409}

        assignment.status = AssignmentStatus.FAILED
        assignment.failed_at = datetime.now(UTC)
        assignment.failure_reason = f"{reason}: {description}" if description else reason

        # Update order
        order = await self._db.scalar(select(Order).where(Order.id == assignment.order_id))
        if order:
            order.status = OrderStatus.FAILED

        # Partial pay: 50% of base
        partial_pay = 12.50
        earnings = PartnerEarnings(
            partner_id=partner.id,
            assignment_id=assignment.id,
            order_id=assignment.order_id,
            base_pay=partial_pay,
            distance_pay=0,
            surge_pay=0,
            total_earned=partial_pay,
        )
        self._db.add(earnings)

        partner.wallet_balance = float(partner.wallet_balance or 0) + partial_pay

        await self._db.flush()

        return {
            "status": "FAILED",
            "partial_pay": partial_pay,
            "message": "Partial payment added to wallet. Return food to restaurant or dispose as per your city's policy.",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIVE + HISTORY
    # ══════════════════════════════════════════════════════════════════════════

    async def get_active_assignment(self, partner: DeliveryPartner) -> dict | None:
        """Fetch the partner's currently active assignment, if any."""
        active_statuses = [
            AssignmentStatus.ASSIGNED,
            AssignmentStatus.ACCEPTED,
            AssignmentStatus.REACHED_RESTAURANT,
            AssignmentStatus.PICKED_UP,
            AssignmentStatus.REACHED_CUSTOMER,
        ]
        assignment = await self._db.scalar(
            select(DeliveryAssignment)
            .options(
                selectinload(DeliveryAssignment.delivery_otp),
                joinedload(DeliveryAssignment.order).joinedload(Order.restaurant),
            )
            .where(
                DeliveryAssignment.partner_id == partner.id,
                DeliveryAssignment.status.in_(active_statuses),
            )
        )
        if not assignment:
            return None

        otp_record = assignment.delivery_otp
        order = assignment.order
        restaurant = order.restaurant if order else None

        waypoints = [
            {
                "step": 1,
                "type": "PICKUP",
                "label": restaurant.name if restaurant else "Restaurant",
                "address": restaurant.full_address if restaurant else "",
                "latitude": float(assignment.restaurant_latitude) if assignment.restaurant_latitude else None,
                "longitude": float(assignment.restaurant_longitude) if assignment.restaurant_longitude else None,
                "instructions": "Show this order ID at counter",
            },
            {
                "step": 2,
                "type": "DELIVERY",
                "label": f"Customer: {assignment.customer_name or 'Customer'}",
                "address": assignment.customer_address or "",
                "latitude": float(assignment.customer_latitude) if assignment.customer_latitude else None,
                "longitude": float(assignment.customer_longitude) if assignment.customer_longitude else None,
                "instructions": "Call customer if door is closed",
                "delivery_otp": otp_record.otp if otp_record else None,
            },
        ]

        return {
            "assignment_id": str(assignment.id),
            "order_id": str(assignment.order_id),
            "status": assignment.status.value,
            "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
            "accepted_at": assignment.accepted_at.isoformat() if assignment.accepted_at else None,
            "distance_km": float(assignment.distance_km) if assignment.distance_km else None,
            "customer_address": assignment.customer_address,
            "customer_name": assignment.customer_name,
            "waypoints": waypoints,
        }

    async def get_assignment_history(
        self, partner: DeliveryPartner, page: int = 1, limit: int = 20, status_filter: str | None = None
    ) -> dict:
        """Paginated assignment history."""
        query = select(DeliveryAssignment).where(
            DeliveryAssignment.partner_id == partner.id
        )
        count_query = select(func.count(DeliveryAssignment.id)).where(
            DeliveryAssignment.partner_id == partner.id
        )

        if status_filter:
            try:
                st = AssignmentStatus(status_filter)
                query = query.where(DeliveryAssignment.status == st)
                count_query = count_query.where(DeliveryAssignment.status == st)
            except ValueError:
                pass

        total = await self._db.scalar(count_query) or 0
        offset = (page - 1) * limit

        result = await self._db.execute(
            query.order_by(DeliveryAssignment.assigned_at.desc())
            .offset(offset).limit(limit)
        )
        assignments = result.scalars().all()

        items = []
        for a in assignments:
            items.append({
                "assignment_id": str(a.id),
                "order_id": str(a.order_id),
                "status": a.status.value,
                "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
                "delivered_at": a.delivered_at.isoformat() if a.delivered_at else None,
                "distance_km": float(a.distance_km) if a.distance_km else None,
                "customer_address": a.customer_address,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if limit else 1,
        }
