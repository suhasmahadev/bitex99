from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from app.models.menu import MenuCategory, MenuItem
from app.models.order import Order, OrderItem, OrderStatus, PaymentMethod
from app.models.restaurant_partner import BusinessType, RestaurantPartner
from app.models.user import User
from app.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def restaurant_partner_context(db_session, seeded_restaurant):
    user = User(
        phone="+919000000001",
        name="Partner One",
        is_verified=True,
        role="RESTAURANT_PARTNER",
        restaurant_status="DOCS_APPROVED",
    )
    db_session.add(user)
    await db_session.flush()
    partner = RestaurantPartner(
        user_id=user.id,
        restaurant_id=seeded_restaurant.id,
        owner_name="Partner One",
        business_type=BusinessType.RESTAURANT,
        fssai_number="12345678901234",
        commission_rate=20,
    )
    db_session.add(partner)
    await db_session.commit()
    token = create_access_token(
        user.id,
        user.phone,
        role="RESTAURANT_PARTNER",
        restaurant_partner_id=partner.id,
        restaurant_id=seeded_restaurant.id,
    )
    return user, partner, {"Authorization": f"Bearer {token}"}


async def _add_order(db, user_id, restaurant_id, total, status=OrderStatus.DELIVERED, created_at=None):
    order = Order(
        user_id=user_id,
        restaurant_id=restaurant_id,
        delivery_address_snapshot={"full_address": "Test"},
        items_total=total,
        delivery_fee=0,
        discount_amount=0,
        total_amount=total,
        payment_method=PaymentMethod.COD,
        status=status,
        created_at=created_at or datetime.now(UTC),
        delivered_at=datetime.now(UTC) if status == OrderStatus.DELIVERED else None,
    )
    db.add(order)
    await db.flush()
    return order


@pytest.mark.asyncio
async def test_overview_returns_correct_today_totals(client, db_session, restaurant_partner_context):
    user, partner, headers = restaurant_partner_context
    for total in (100, 200, 300):
        await _add_order(db_session, user.id, partner.restaurant_id, total)
    await db_session.commit()

    response = await client.get("/api/v1/restaurant/analytics/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["today"]["orders"] == 3
    assert data["today"]["revenue"] == 600.0


@pytest.mark.asyncio
async def test_overview_cancellation_rate(client, db_session, restaurant_partner_context):
    user, partner, headers = restaurant_partner_context
    await _add_order(db_session, user.id, partner.restaurant_id, 100, OrderStatus.CANCELLED)
    for _ in range(4):
        await _add_order(db_session, user.id, partner.restaurant_id, 100)
    await db_session.commit()

    response = await client.get("/api/v1/restaurant/analytics/overview", headers=headers)
    assert response.status_code == 200
    assert response.json()["today"]["cancellation_rate"] == 20.0


@pytest.mark.asyncio
async def test_revenue_chart_7days_has_7_labels(client, restaurant_partner_context):
    _, _, headers = restaurant_partner_context
    response = await client.get("/api/v1/restaurant/analytics/revenue-chart?period=7days", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["labels"]) == 7
    assert len(data["revenue"]) == 7


@pytest.mark.asyncio
async def test_top_items_sorted_by_order_count(client, db_session, restaurant_partner_context):
    user, partner, headers = restaurant_partner_context
    category = MenuCategory(restaurant_id=partner.restaurant_id, name="Top")
    db_session.add(category)
    await db_session.flush()
    item1 = MenuItem(restaurant_id=partner.restaurant_id, category_id=category.id, name="A", price=10, is_veg=True)
    item2 = MenuItem(restaurant_id=partner.restaurant_id, category_id=category.id, name="B", price=20, is_veg=True)
    db_session.add_all([item1, item2])
    await db_session.flush()
    order1 = await _add_order(db_session, user.id, partner.restaurant_id, 40)
    order2 = await _add_order(db_session, user.id, partner.restaurant_id, 10)
    db_session.add_all([
        OrderItem(order_id=order1.id, menu_item_id=item1.id, name="A", price=10, quantity=2),
        OrderItem(order_id=order1.id, menu_item_id=item2.id, name="B", price=20, quantity=1),
        OrderItem(order_id=order2.id, menu_item_id=item1.id, name="A", price=10, quantity=1),
    ])
    await db_session.commit()

    response = await client.get("/api/v1/restaurant/analytics/top-items?limit=3", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["rank"] == 1
    assert items[0]["order_count"] >= items[1]["order_count"]


@pytest.mark.asyncio
async def test_peak_hours_has_24_entries(client, restaurant_partner_context):
    _, _, headers = restaurant_partner_context
    response = await client.get("/api/v1/restaurant/analytics/peak-hours", headers=headers)
    assert response.status_code == 200
    assert len(response.json()["hours"]) == 24
