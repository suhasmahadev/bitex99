"""
Order service — placement, lifecycle transitions, cancellation, history.
ALL placement logic runs inside ONE database transaction (async with db.begin()).
"""

import uuid
from datetime import UTC, datetime
import asyncio

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.exceptions import (
    AddressNotFoundError,
    EmptyCartError,
    ForbiddenError,
    OrderNotFoundError,
    RestaurantClosedError,
)
from app.models.address import Address
from app.models.cart import CartItem
from app.models.coupon import Coupon
from app.models.menu import MenuItem
from app.models.order import (
    VALID_TRANSITIONS,
    Order,
    OrderItem,
    OrderStatus,
    PaymentStatus,
    USER_CANCELLABLE_STATUSES,
)
from app.models.restaurant import Restaurant
from app.schemas.order import (
    CancelOrderRequest,
    OrderItemResponse,
    OrderListItem,
    OrderResponse,
    OrderRestaurantInfo,
    PlaceOrderRequest,
    UpdateOrderStatusRequest,
)
from app.utils.pagination import PaginatedResponse, PaginationParams

from fastapi import status
from fastapi.responses import JSONResponse


class OrderServiceError(Exception):
    """Service-level error that carries a JSONResponse."""

    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__()


class OrderService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── PART A: Place Order (transactional) ──────────────────────────────────

    async def place_order(
        self, user_id: uuid.UUID, data: PlaceOrderRequest
    ) -> OrderResponse:
        """
        Execute all 12 steps inside ONE transaction.
        If any step fails, everything rolls back.
        """

        # Step 1: Fetch cart items — fail before transaction if empty
        cart_res = await self._db.execute(
            select(CartItem)
            .where(CartItem.user_id == user_id)
            .order_by(CartItem.added_at.asc())
        )
        cart_items = list(cart_res.scalars().all())
        if not cart_items:
            raise EmptyCartError()

        restaurant_id = cart_items[0].restaurant_id

        # Step 2: Fetch restaurant — check is_open
        rest_res = await self._db.execute(
            select(Restaurant).where(Restaurant.id == restaurant_id)
        )
        restaurant = rest_res.scalar_one()
        if not restaurant.is_open:
            raise RestaurantClosedError()

        # Step 3: Fetch ALL menu items in ONE query — check availability
        menu_item_ids = [ci.menu_item_id for ci in cart_items]
        mi_res = await self._db.execute(
            select(MenuItem).where(MenuItem.id.in_(menu_item_ids))
        )
        menu_items_map: dict[uuid.UUID, MenuItem] = {
            mi.id: mi for mi in mi_res.scalars().all()
        }
        unavailable = [
            menu_items_map[mid].name
            for mid in menu_item_ids
            if mid in menu_items_map and not menu_items_map[mid].is_available
        ]
        if unavailable:
            raise OrderServiceError(
                status.HTTP_409_CONFLICT,
                {
                    "success": False,
                    "error_code": "ITEM_UNAVAILABLE",
                    "message": "Some items are no longer available",
                    "unavailable_items": unavailable,
                },
            )

        # Step 4: Validate delivery address belongs to current user
        addr_res = await self._db.execute(
            select(Address).where(Address.id == data.delivery_address_id)
        )
        address = addr_res.scalar_one_or_none()
        if address is None or address.user_id != user_id:
            raise AddressNotFoundError()

        # Step 6 (partial): Compute items_total using effective_price
        items_total = 0.0
        for ci in cart_items:
            mi = menu_items_map[ci.menu_item_id]
            eff = (
                float(mi.discounted_price)
                if mi.discounted_price is not None
                else float(mi.price)
            )
            items_total += eff * ci.quantity
        items_total = round(items_total, 2)

        # Step 5: Coupon validation (only if provided)
        discount_amount = 0.0
        coupon: Coupon | None = None
        if data.coupon_code:
            coupon, discount_amount = await self._validate_and_compute_coupon(
                data.coupon_code.upper(), items_total
            )

        # Step 6 (complete): Compute all amounts
        delivery_fee = float(restaurant.delivery_fee)
        total_amount = round(items_total + delivery_fee - discount_amount, 2)

        # Validate min order
        if total_amount < float(restaurant.min_order_amount):
            raise OrderServiceError(
                status.HTTP_400_BAD_REQUEST,
                {
                    "success": False,
                    "error_code": "MIN_ORDER_NOT_MET",
                    "message": "Order total is below minimum order amount",
                    "min_order_amount": float(restaurant.min_order_amount),
                    "current_total": total_amount,
                },
            )

        # Step 7: Snapshot delivery address as JSONB
        delivery_address_snapshot = {
            "label": address.label.value if hasattr(address.label, "value") else str(address.label),
            "full_address": address.full_address,
            "landmark": address.landmark,
            "latitude": float(address.latitude) if address.latitude else None,
            "longitude": float(address.longitude) if address.longitude else None,
        }

        # Steps 8-11: ALL inside one transaction
        # Step 8: Create Order
        order = Order(
            user_id=user_id,
            restaurant_id=restaurant_id,
            delivery_address_id=data.delivery_address_id,
            delivery_address_snapshot=delivery_address_snapshot,
            items_total=items_total,
            delivery_fee=delivery_fee,
            discount_amount=discount_amount,
            total_amount=total_amount,
            coupon_code=data.coupon_code.upper() if data.coupon_code else None,
            payment_method=data.payment_method,
            status=OrderStatus.PLACED,
            payment_status=PaymentStatus.PENDING,
        )
        self._db.add(order)
        await self._db.flush()

        # Step 9: Create OrderItem records — snapshot name + effective price
        for ci in cart_items:
            mi = menu_items_map[ci.menu_item_id]
            eff_price = (
                float(mi.discounted_price)
                if mi.discounted_price is not None
                else float(mi.price)
            )
            self._db.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=ci.menu_item_id,
                    name=mi.name,
                    price=eff_price,
                    quantity=ci.quantity,
                )
            )

        # Step 10: Increment coupon.used_count
        if coupon is not None:
            coupon.used_count += 1

        # Step 11: DELETE all cart items (same transaction)
        await self._db.execute(
            delete(CartItem).where(CartItem.user_id == user_id)
        )

        # Step 12: Flush — commit handled by session middleware
        await self._db.flush()

        # Trigger auto-assign in background AFTER transaction commits
        # Uses its own DB session to avoid stale state
        from app.services.assignment_service import AssignmentService
        from app.redis_client import get_redis

        async def _trigger_assign():
            """Wait briefly for commit, then assign + notify restaurant."""
            await asyncio.sleep(0.5)  # Let the session middleware commit first
            try:
                redis = get_redis()
                async with AsyncSessionLocal() as db:
                    svc = AssignmentService(db, redis)
                    await svc.auto_assign_partner(order.id)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Auto-assign failed: %s", e)

            # Notify restaurant via WS
            try:
                from app.utils.notification_service import notify_restaurant_new_order
                async with AsyncSessionLocal() as db:
                    fresh_order = await db.get(Order, order.id)
                    if fresh_order is not None:
                        await notify_restaurant_new_order(order.restaurant_id, fresh_order, db)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("notify_restaurant failed: %s", e)

        asyncio.create_task(_trigger_assign())

        # Auto-reject after 90s if restaurant doesn't respond
        async def _auto_reject():
            await asyncio.sleep(0.5)
            try:
                from app.utils.notification_service import auto_reject_timeout
                async with AsyncSessionLocal() as db:
                    await auto_reject_timeout(order.id, order.restaurant_id, db)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("auto_reject_timeout failed: %s", e)

        asyncio.create_task(_auto_reject())

        # Reload for serialization
        return await self.get_order(user_id, order.id)

    # ── PART B: Status Transitions ───────────────────────────────────────────

    async def update_status(
        self, order_id: uuid.UUID, new_status: OrderStatus
    ) -> OrderResponse:
        """Internal / webhook — advances order status with transition guard."""
        order = await self._load_order(order_id)
        allowed = VALID_TRANSITIONS.get(order.status, [])
        if new_status not in allowed:
            raise OrderServiceError(
                status.HTTP_409_CONFLICT,
                {
                    "success": False,
                    "error_code": "INVALID_STATUS_TRANSITION",
                    "message": f"Cannot move from {order.status.value} to {new_status.value}",
                    "current_status": order.status.value,
                    "requested_status": new_status.value,
                },
            )
        order.status = new_status
        if new_status == OrderStatus.DELIVERED:
            order.delivered_at = datetime.now(UTC)
        await self._db.flush()
        return self._serialize(order)

    # ── PART C: Cancellation ─────────────────────────────────────────────────

    async def cancel_order(
        self, user_id: uuid.UUID, order_id: uuid.UUID, data: CancelOrderRequest
    ) -> OrderResponse:
        """Cancel order — only from PLACED or CONFIRMED."""
        order = await self._load_order(order_id)

        # 1. Verify ownership
        if order.user_id != user_id:
            raise ForbiddenError()

        # 2. Check status is cancellable
        if order.status not in USER_CANCELLABLE_STATUSES:
            raise OrderServiceError(
                status.HTTP_409_CONFLICT,
                {
                    "success": False,
                    "error_code": "INVALID_STATUS_TRANSITION",
                    "message": "Order cannot be cancelled after preparation has started",
                },
            )

        # 3. Update status
        order.status = OrderStatus.CANCELLED

        # 4. Set cancellation reason
        order.cancellation_reason = data.reason

        # 5. If payment was successful, mark as refunded
        if order.payment_status == PaymentStatus.SUCCESS:
            order.payment_status = PaymentStatus.REFUNDED

        await self._db.flush()

        # 6. Return updated order
        return self._serialize(order)

    # ── PART D: Listing & Detail ─────────────────────────────────────────────

    async def get_order(
        self, user_id: uuid.UUID, order_id: uuid.UUID
    ) -> OrderResponse:
        order = await self._load_order(order_id)
        if order.user_id != user_id:
            raise ForbiddenError()
        return self._serialize(order)

    async def list_orders(
        self,
        user_id: uuid.UUID,
        pagination: PaginationParams,
        status_filter: str | None = None,
    ) -> PaginatedResponse:
        query = select(Order).options(
            selectinload(Order.restaurant),
            selectinload(Order.items)
        ).where(Order.user_id == user_id)
        count_query = select(func.count(Order.id)).where(Order.user_id == user_id)

        if status_filter:
            try:
                os = OrderStatus(status_filter)
                query = query.where(Order.status == os)
                count_query = count_query.where(Order.status == os)
            except ValueError:
                pass

        count_res = await self._db.execute(count_query)
        total = count_res.scalar_one()

        result = await self._db.execute(
            query.order_by(Order.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        orders = result.scalars().all()
        items = [self._serialize_list(o) for o in orders]
        return PaginatedResponse.create(items, total, pagination)

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _load_order(self, order_id: uuid.UUID) -> Order:
        result = await self._db.execute(
            select(Order).options(
                selectinload(Order.restaurant),
                selectinload(Order.items)
            ).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise OrderNotFoundError()
        return order

    async def _validate_and_compute_coupon(
        self, code: str, items_total: float
    ) -> tuple[Coupon, float]:
        """Full coupon validation per SPEC Step 5."""
        result = await self._db.execute(
            select(Coupon).where(Coupon.code == code)
        )
        coupon = result.scalar_one_or_none()

        if coupon is None:
            raise OrderServiceError(
                status.HTTP_400_BAD_REQUEST,
                {"success": False, "error_code": "COUPON_INVALID", "message": "Coupon not found"},
            )

        if not coupon.is_active:
            raise OrderServiceError(
                status.HTTP_400_BAD_REQUEST,
                {"success": False, "error_code": "COUPON_INVALID", "message": "Coupon is no longer active"},
            )

        now = datetime.now(UTC)
        if coupon.valid_from and coupon.valid_from.replace(tzinfo=None) > now.replace(tzinfo=None):
            raise OrderServiceError(
                status.HTTP_400_BAD_REQUEST,
                {"success": False, "error_code": "COUPON_EXPIRED", "message": "Coupon is not yet valid"},
            )
        if coupon.valid_until and coupon.valid_until.replace(tzinfo=None) < now.replace(tzinfo=None):
            raise OrderServiceError(
                status.HTTP_400_BAD_REQUEST,
                {"success": False, "error_code": "COUPON_EXPIRED", "message": "Coupon has expired"},
            )

        if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
            raise OrderServiceError(
                status.HTTP_400_BAD_REQUEST,
                {"success": False, "error_code": "COUPON_INVALID", "message": "Coupon usage limit reached"},
            )

        if items_total < float(coupon.min_order_amount):
            raise OrderServiceError(
                status.HTTP_400_BAD_REQUEST,
                {
                    "success": False,
                    "error_code": "COUPON_MIN_ORDER",
                    "message": f"Minimum order amount is {float(coupon.min_order_amount)}",
                },
            )

        # Calculate discount
        from app.models.coupon import DiscountType

        if coupon.discount_type == DiscountType.PERCENT:
            disc = items_total * float(coupon.discount_value) / 100
            if coupon.max_discount is not None:
                disc = min(disc, float(coupon.max_discount))
        else:  # FLAT
            disc = float(coupon.discount_value)

        return coupon, round(min(disc, items_total), 2)

    # ── Serialization ────────────────────────────────────────────────────────

    @staticmethod
    def _serialize(order: Order) -> OrderResponse:
        rest = order.restaurant
        return OrderResponse(
            id=order.id,
            status=order.status,
            payment_method=order.payment_method,
            payment_status=order.payment_status,
            restaurant=OrderRestaurantInfo(
                id=rest.id,
                name=rest.name,
                image_url=rest.image_url,
            ),
            delivery_address=order.delivery_address_snapshot,
            items=[
                OrderItemResponse(
                    menu_item_id=i.menu_item_id,
                    name=i.name,
                    price=float(i.price),
                    quantity=int(i.quantity),
                    item_total=round(float(i.price) * int(i.quantity), 2),
                )
                for i in order.items
            ],
            items_total=float(order.items_total),
            delivery_fee=float(order.delivery_fee),
            discount_amount=float(order.discount_amount),
            coupon_code=order.coupon_code,
            total_amount=float(order.total_amount),
            cancellation_reason=order.cancellation_reason,
            estimated_delivery_at=order.estimated_delivery_at,
            created_at=order.created_at,
        )

    @staticmethod
    def _serialize_list(order: Order) -> OrderListItem:
        rest_name = order.restaurant.name if order.restaurant else None
        item_count = sum(int(i.quantity) for i in order.items)
        return OrderListItem(
            id=order.id,
            status=order.status,
            payment_status=order.payment_status,
            total_amount=float(order.total_amount),
            restaurant_name=rest_name,
            item_count=item_count,
            created_at=order.created_at,
        )
