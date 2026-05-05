"""
Order management service — restaurant-side order operations.
Handles live orders, status transitions, accept/reject flows.
Uses correct Order.items relationship (not order_items).
"""
import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.models.order import Order, OrderItem
from app.models.order_response import OrderResponse, OrderResponseAction
from app.models.restaurant_partner import RestaurantPartner

logger = logging.getLogger(__name__)


class OrderManagementService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def verify_restaurant_ownership(
        self, restaurant_id: uuid.UUID, partner_id: uuid.UUID
    ) -> RestaurantPartner:
        partner = await self._db.scalar(
            select(RestaurantPartner).where(RestaurantPartner.id == partner_id)
        )
        if not partner or partner.restaurant_id != restaurant_id:
            raise HTTPException(status_code=403, detail="Not your restaurant")
        return partner

    def _serialize_order(self, order: Order) -> dict:
        return {
            "id": str(order.id),
            "order_number": f"#{str(order.id)[-6:].upper()}",
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
            "items_total": float(order.items_total),
            "delivery_fee": float(order.delivery_fee),
            "total_amount": float(order.total_amount),
            "payment_method": (
                order.payment_method.value
                if hasattr(order.payment_method, "value")
                else str(order.payment_method)
            ),
            "payment_status": (
                order.payment_status.value
                if hasattr(order.payment_status, "value")
                else str(order.payment_status)
            ),
            "customer_name": (
                order.delivery_address_snapshot.get("label", "Customer")
                if order.delivery_address_snapshot
                else "Customer"
            ),
            "delivery_address": (
                order.delivery_address_snapshot.get("full_address")
                if order.delivery_address_snapshot
                else None
            ),
            "created_at": order.created_at.isoformat(),
            "estimated_delivery_at": (
                order.estimated_delivery_at.isoformat()
                if order.estimated_delivery_at
                else None
            ),
            "preparation_time": order.preparation_time,
            "items": [
                {
                    "name": item.name,
                    "quantity": int(item.quantity),
                    "price": float(item.price),
                    "item_total": float(item.price * item.quantity),
                }
                for item in order.items
            ],
        }

    async def get_live_orders(self, restaurant_id: uuid.UUID) -> dict:
        orders = await self._db.scalars(
            select(Order)
            .where(
                Order.restaurant_id == restaurant_id,
                Order.status.in_(["PLACED", "CONFIRMED", "PREPARING", "READY_FOR_PICKUP"]),
            )
            .options(selectinload(Order.items))
            .order_by(Order.created_at.asc())
        )

        result = {"placed": [], "confirmed": [], "preparing": [], "ready": []}

        for order in orders.all():
            data = self._serialize_order(order)
            status = data["status"]
            if status == "PLACED":
                result["placed"].append(data)
            elif status == "CONFIRMED":
                result["confirmed"].append(data)
            elif status == "PREPARING":
                result["preparing"].append(data)
            elif status == "READY_FOR_PICKUP":
                result["ready"].append(data)

        return result

    async def get_orders(
        self,
        restaurant_id: uuid.UUID,
        status: str = None,
        date_from: str = None,
        date_to: str = None,
        search: str = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        q = select(Order).where(Order.restaurant_id == restaurant_id)
        count_q = select(func.count()).select_from(
            select(Order).where(Order.restaurant_id == restaurant_id).subquery()
        )

        if status:
            q = q.where(Order.status == status)

        total = await self._db.scalar(count_q)
        q = (
            q.options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        orders = await self._db.scalars(q)

        items = []
        for order in orders.all():
            items.append({
                "id": str(order.id),
                "order_number": f"#{str(order.id)[-6:].upper()}",
                "status": order.status.value if hasattr(order.status, "value") else str(order.status),
                "total_amount": float(order.total_amount),
                "payment_method": (
                    order.payment_method.value
                    if hasattr(order.payment_method, "value")
                    else str(order.payment_method)
                ),
                "customer_name": (
                    order.delivery_address_snapshot.get("label", "Customer")
                    if order.delivery_address_snapshot
                    else "Customer"
                ),
                "items_count": sum(int(i.quantity) for i in order.items),
                "created_at": order.created_at.isoformat(),
            })

        return {"items": items, "total": total, "page": page, "limit": limit}

    async def get_order_detail(
        self, order_id: uuid.UUID, restaurant_id: uuid.UUID
    ) -> dict:
        order = await self._db.scalar(
            select(Order)
            .where(Order.id == order_id, Order.restaurant_id == restaurant_id)
            .options(selectinload(Order.items))
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Load response separately (no backreference on Order)
        resp = await self._db.scalar(
            select(OrderResponse).where(OrderResponse.order_id == order_id)
        )

        detail = self._serialize_order(order)
        detail["response"] = (
            {
                "action": resp.action.value if hasattr(resp.action, "value") else str(resp.action),
                "preparation_time": resp.preparation_time,
                "rejection_reason": resp.rejection_reason,
                "responded_at": resp.responded_at.isoformat(),
            }
            if resp
            else None
        )
        return detail

    async def accept_order(
        self,
        order_id: uuid.UUID,
        restaurant_id: uuid.UUID,
        preparation_time: int,
        redis: aioredis.Redis,
    ) -> dict:
        order = await self._db.scalar(
            select(Order)
            .where(Order.id == order_id, Order.restaurant_id == restaurant_id)
            .options(selectinload(Order.items))
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        status = order.status.value if hasattr(order.status, "value") else str(order.status)
        if status != "PLACED":
            raise HTTPException(status_code=409, detail="INVALID_STATUS_TRANSITION")

        # Record response
        existing_resp = await self._db.scalar(
            select(OrderResponse).where(OrderResponse.order_id == order_id)
        )
        if not existing_resp:
            resp = OrderResponse(
                order_id=order.id,
                restaurant_id=restaurant_id,
                action=OrderResponseAction.ACCEPTED,
                preparation_time=preparation_time,
            )
            self._db.add(resp)

        order.status = "CONFIRMED"
        order.preparation_time = preparation_time
        order.restaurant_confirmed_at = func.now()

        await self._db.commit()
        await self._db.refresh(order)

        # Notify customer
        try:
            from app.main import manager
            await manager.send_to_user(
                str(order.user_id),
                {
                    "event": "ORDER_CONFIRMED",
                    "preparation_time": preparation_time,
                    "message": f"Your order is confirmed! Ready in {preparation_time} mins 🍳",
                },
            )
        except Exception as e:
            logger.warning("Failed to notify customer: %s", e)

        return self._serialize_order(order)

    async def reject_order(
        self,
        order_id: uuid.UUID,
        restaurant_id: uuid.UUID,
        reason: str,
        description: str,
    ) -> dict:
        order = await self._db.scalar(
            select(Order)
            .where(Order.id == order_id, Order.restaurant_id == restaurant_id)
            .options(selectinload(Order.items))
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        status = order.status.value if hasattr(order.status, "value") else str(order.status)
        if status != "PLACED":
            raise HTTPException(status_code=409, detail="INVALID_STATUS_TRANSITION")

        cancellation = f"{reason}: {description}" if description else reason

        existing_resp = await self._db.scalar(
            select(OrderResponse).where(OrderResponse.order_id == order_id)
        )
        if not existing_resp:
            resp = OrderResponse(
                order_id=order.id,
                restaurant_id=restaurant_id,
                action=OrderResponseAction.REJECTED,
                rejection_reason=cancellation,
            )
            self._db.add(resp)

        order.status = "CANCELLED"
        order.cancellation_reason = cancellation

        await self._db.commit()
        await self._db.refresh(order)

        try:
            from app.main import manager
            await manager.send_to_user(
                str(order.user_id),
                {
                    "event": "ORDER_CANCELLED",
                    "reason": "Restaurant is unable to fulfil your order",
                    "message": "We're sorry! Refund will be initiated.",
                },
            )
        except Exception as e:
            logger.warning("Failed to notify customer: %s", e)

        return self._serialize_order(order)

    async def mark_preparing(
        self, order_id: uuid.UUID, restaurant_id: uuid.UUID
    ) -> dict:
        order = await self._db.scalar(
            select(Order)
            .where(Order.id == order_id, Order.restaurant_id == restaurant_id)
            .options(selectinload(Order.items))
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        status = order.status.value if hasattr(order.status, "value") else str(order.status)
        if status != "CONFIRMED":
            raise HTTPException(status_code=409, detail="INVALID_STATUS_TRANSITION")

        order.status = "PREPARING"
        await self._db.commit()
        await self._db.refresh(order)

        try:
            from app.main import manager
            await manager.send_to_user(
                str(order.user_id),
                {"event": "ORDER_PREPARING", "message": "Chef is preparing your food 👨‍🍳"},
            )
        except Exception as e:
            logger.warning("Failed to notify customer: %s", e)

        return self._serialize_order(order)

    async def mark_ready(
        self, order_id: uuid.UUID, restaurant_id: uuid.UUID
    ) -> dict:
        order = await self._db.scalar(
            select(Order)
            .where(Order.id == order_id, Order.restaurant_id == restaurant_id)
            .options(selectinload(Order.items))
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        status = order.status.value if hasattr(order.status, "value") else str(order.status)
        if status != "PREPARING":
            raise HTTPException(status_code=409, detail="INVALID_STATUS_TRANSITION")

        order.status = "READY_FOR_PICKUP"
        order.ready_at = datetime.now(UTC)
        await self._db.commit()
        await self._db.refresh(order)

        try:
            from app.main import manager
            await manager.send_to_user(
                str(order.user_id),
                {"event": "ORDER_READY", "message": "Food is ready! Picking up soon 🛵"},
            )
        except Exception as e:
            logger.warning("Failed to notify customer: %s", e)

        return self._serialize_order(order)
