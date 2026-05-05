"""
Cart service — all business logic for cart management.
Enforces: single-restaurant constraint, availability checks, quantity merging,
and computed totals with effective_price (discounted_price ?? price).
"""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.exceptions import (
    MenuItemNotFoundError,
    NotFoundError,
    RestaurantClosedError,
)
from app.models.cart import CartItem
from app.models.menu import MenuItem
from app.models.restaurant import Restaurant
from app.schemas.cart import (
    AddToCartRequest,
    CartConflictData,
    CartConflictResponse,
    CartData,
    CartItemResponse,
    CartResponse,
    CartRestaurantInfo,
    RemoveFromCartRequest,
    RestaurantBrief,
    UpdateQuantityRequest,
)


class ItemUnavailableError(Exception):
    """Raised when a menu item is not available."""
    pass


class CartConflictError(Exception):
    """Raised when adding an item from a different restaurant."""

    def __init__(self, response: CartConflictResponse) -> None:
        self.response = response
        super().__init__()


class CartService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── GET /cart ─────────────────────────────────────────────────────────────

    async def get_cart(self, user_id: uuid.UUID) -> CartResponse:
        """Return the full cart with computed totals."""
        items = await self._fetch_cart_items(user_id)
        return self._build_cart_response(items)

    # ── POST /cart/add ────────────────────────────────────────────────────────

    async def add_item(self, user_id: uuid.UUID, data: AddToCartRequest) -> CartResponse:
        """
        Add item to cart. Exact order per SPEC Section 6:
        1. Fetch menu_item — 404 if not found
        2. Check is_available — 409 ITEM_UNAVAILABLE if false
        3. Fetch restaurant — 409 RESTAURANT_CLOSED if not open
        4. Check cart conflict (Rule 1)
        5. If same item already in cart → UPDATE quantity += requested
        6. If new → INSERT with restaurant_id from menu_item
        """
        # Step 1: fetch menu item
        menu_item = await self._get_menu_item_or_404(data.menu_item_id)

        # Step 2: check availability
        if not menu_item.is_available:
            raise ItemUnavailableError()

        # Step 3: fetch restaurant and check open status
        restaurant = menu_item.restaurant
        if not restaurant.is_open:
            raise RestaurantClosedError()

        # Step 4: single-restaurant constraint
        existing_items = await self._fetch_cart_items(user_id)
        if existing_items:
            existing_restaurant_id = existing_items[0].restaurant_id
            if existing_restaurant_id != menu_item.restaurant_id:
                existing_restaurant = existing_items[0].restaurant
                raise CartConflictError(
                    CartConflictResponse(
                        success=False,
                        error_code="CART_CONFLICT",
                        message=(
                            f"Your cart has items from {existing_restaurant.name}. "
                            f"Clear cart to add from {restaurant.name}?"
                        ),
                        data=CartConflictData(
                            existing_restaurant=RestaurantBrief(
                                id=str(existing_restaurant_id),
                                name=existing_restaurant.name,
                            ),
                            new_restaurant=RestaurantBrief(
                                id=str(menu_item.restaurant_id),
                                name=restaurant.name,
                            ),
                        ),
                    )
                )

        # Step 5 & 6: upsert — merge quantity if exists, else insert
        existing_cart_item = await self._find_cart_item_by_menu(user_id, data.menu_item_id)
        if existing_cart_item:
            existing_cart_item.quantity += data.quantity
        else:
            new_item = CartItem(
                user_id=user_id,
                menu_item_id=data.menu_item_id,
                restaurant_id=menu_item.restaurant_id,
                quantity=data.quantity,
            )
            self._db.add(new_item)

        await self._db.flush()
        return await self.get_cart(user_id)

    # ── POST /cart/update-quantity ─────────────────────────────────────────────

    async def update_quantity(
        self, user_id: uuid.UUID, data: UpdateQuantityRequest
    ) -> CartResponse:
        """
        Update quantity of a cart item.
        quantity = 0 → DELETE the item.
        quantity >= 1 → SET quantity to new value.
        """
        cart_item = await self._find_cart_item_by_menu(user_id, data.menu_item_id)
        if cart_item is None:
            raise NotFoundError(detail="Item not in cart")

        if data.quantity == 0:
            await self._db.delete(cart_item)
        else:
            cart_item.quantity = data.quantity

        await self._db.flush()
        return await self.get_cart(user_id)

    # ── POST /cart/remove ─────────────────────────────────────────────────────

    async def remove_item(
        self, user_id: uuid.UUID, data: RemoveFromCartRequest
    ) -> CartResponse:
        """Remove a specific item from the cart."""
        cart_item = await self._find_cart_item_by_menu(user_id, data.menu_item_id)
        if cart_item is None:
            raise NotFoundError(detail="Item not in cart")

        await self._db.delete(cart_item)
        await self._db.flush()
        return await self.get_cart(user_id)

    # ── POST /cart/clear ──────────────────────────────────────────────────────

    async def clear_cart(self, user_id: uuid.UUID) -> CartResponse:
        """Delete all cart items for this user."""
        await self._db.execute(
            delete(CartItem).where(CartItem.user_id == user_id)
        )
        await self._db.flush()
        return self._build_empty_cart()

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_cart_items(self, user_id: uuid.UUID) -> list[CartItem]:
        result = await self._db.execute(
            select(CartItem)
            .options(
                selectinload(CartItem.menu_item),
                selectinload(CartItem.restaurant),
            )
            .where(CartItem.user_id == user_id)
            .order_by(CartItem.added_at.asc())
        )
        return list(result.scalars().all())

    async def _find_cart_item_by_menu(
        self, user_id: uuid.UUID, menu_item_id: uuid.UUID
    ) -> CartItem | None:
        result = await self._db.execute(
            select(CartItem).where(
                CartItem.user_id == user_id,
                CartItem.menu_item_id == menu_item_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_menu_item_or_404(self, item_id: uuid.UUID) -> MenuItem:
        result = await self._db.execute(
            select(MenuItem)
            .options(joinedload(MenuItem.restaurant))
            .where(MenuItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise MenuItemNotFoundError()
        return item

    async def _get_restaurant(self, restaurant_id: uuid.UUID) -> Restaurant:
        result = await self._db.execute(
            select(Restaurant).where(Restaurant.id == restaurant_id)
        )
        return result.scalar_one()

    @staticmethod
    def _build_empty_cart() -> CartResponse:
        return CartResponse(
            success=True,
            data=CartData(
                restaurant=None,
                items=[],
                items_total=0,
                cart_subtotal=0,
                delivery_fee=0,
                grand_total=0,
                item_count=0,
            ),
        )

    def _build_cart_response(self, cart_items: list[CartItem]) -> CartResponse:
        if not cart_items:
            return self._build_empty_cart()

        items: list[CartItemResponse] = []
        cart_subtotal = 0.0
        restaurant_info: CartRestaurantInfo | None = None

        for ci in cart_items:
            mi = ci.menu_item
            # effective_price = discounted_price if not NULL else price
            eff_price = (
                float(mi.discounted_price)
                if mi.discounted_price is not None
                else float(mi.price)
            )
            item_total = round(eff_price * ci.quantity, 2)
            cart_subtotal += item_total

            items.append(
                CartItemResponse(
                    menu_item_id=ci.menu_item_id,
                    name=mi.name,
                    quantity=ci.quantity,
                    price=float(mi.price),
                    discounted_price=(
                        float(mi.discounted_price)
                        if mi.discounted_price is not None
                        else None
                    ),
                    effective_price=eff_price,
                    item_total=item_total,
                )
            )

            if restaurant_info is None:
                rest = ci.restaurant
                restaurant_info = CartRestaurantInfo(
                    id=rest.id,
                    name=rest.name,
                    is_open=rest.is_open,
                    delivery_fee=float(rest.delivery_fee),
                )

        cart_subtotal = round(cart_subtotal, 2)
        delivery_fee = restaurant_info.delivery_fee if restaurant_info else 0
        grand_total = round(cart_subtotal + delivery_fee, 2)

        return CartResponse(
            success=True,
            data=CartData(
                restaurant=restaurant_info,
                items=items,
                items_total=cart_subtotal,
                cart_subtotal=cart_subtotal,
                delivery_fee=delivery_fee,
                grand_total=grand_total,
                item_count=len(items),
            ),
        )
