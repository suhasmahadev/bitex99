"""
Notification service — sends real-time events to restaurant and customer WebSocket channels.
Restaurant channel: connection_manager.restaurant_connections[restaurant_id]
Customer channel:   connection_manager.user_connections[user_id]
Redis fallback: buffered list per restaurant for offline restaurants.
"""
import asyncio
import json
import logging
import uuid

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderItem
from app.models.restaurant import Restaurant

logger = logging.getLogger(__name__)


async def notify_restaurant_new_order(
    restaurant_id: uuid.UUID,
    order: Order,
    db: AsyncSession,
):
    """Push NEW_ORDER event to restaurant WS. Falls back to Redis buffer."""
    try:
        from app.redis_client import get_redis
        from app.main import manager

        redis = get_redis()

        # Fetch order items
        items_res = await db.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        order_items = items_res.all()

        # Fetch restaurant name
        restaurant = await db.scalar(select(Restaurant).where(Restaurant.id == restaurant_id))
        restaurant_name = restaurant.name if restaurant else "Restaurant"

        customer_name = (
            order.delivery_address_snapshot.get("label", "Customer")
            if order.delivery_address_snapshot else "Customer"
        )

        message = {
            "event": "NEW_ORDER",
            "order": {
                "order_id": str(order.id),
                "order_number": f"#{str(order.id)[-6:].upper()}",
                "items": [
                    {
                        "name": item.name,
                        "quantity": int(item.quantity),
                        "price": float(item.price),
                        "item_total": float(item.price * item.quantity),
                    }
                    for item in order_items
                ],
                "items_total": float(order.items_total),
                "delivery_fee": float(order.delivery_fee),
                "total_amount": float(order.total_amount),
                "payment_method": order.payment_method.value if hasattr(order.payment_method, "value") else str(order.payment_method),
                "payment_status": order.payment_status.value if hasattr(order.payment_status, "value") else str(order.payment_status),
                "customer_name": customer_name,
                "delivery_address": (
                    order.delivery_address_snapshot.get("full_address")
                    if order.delivery_address_snapshot else None
                ),
                "created_at": order.created_at.isoformat(),
            },
            "expires_in_seconds": 90,
        }

        ws = manager.restaurant_connections.get(str(restaurant_id))
        if ws:
            try:
                await ws.send_json(message)
                logger.info("Sent NEW_ORDER to restaurant WS: %s", restaurant_id)
                return
            except Exception as e:
                logger.warning("WS send failed for restaurant %s: %s", restaurant_id, e)
                manager.restaurant_connections.pop(str(restaurant_id), None)

        # Fallback: buffer in Redis (TTL 1 hour)
        key = f"restaurant:pending:{restaurant_id}"
        await redis.rpush(key, json.dumps(message, default=str))
        await redis.expire(key, 3600)
        logger.info("Buffered NEW_ORDER in Redis for restaurant: %s", restaurant_id)

    except Exception as e:
        logger.error("notify_restaurant_new_order failed: %s", e)


async def auto_reject_timeout(
    order_id: uuid.UUID,
    restaurant_id: uuid.UUID,
    db: AsyncSession,
):
    """Auto-reject order if restaurant doesn't respond in 90 seconds."""
    await asyncio.sleep(90)
    try:
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as fresh_db:
            from sqlalchemy import select
            from app.models.order import Order

            order = await fresh_db.scalar(select(Order).where(Order.id == order_id))
            if order and order.status == "PLACED":
                from app.services.order_management_service import OrderManagementService
                svc = OrderManagementService(fresh_db)
                await svc.reject_order(
                    order_id=order_id,
                    restaurant_id=restaurant_id,
                    reason="OTHER",
                    description="Restaurant did not respond in time",
                )
                logger.info("Order %s auto-rejected after 90s timeout", order_id)
    except Exception as e:
        logger.error("auto_reject_timeout failed for order %s: %s", order_id, e)
