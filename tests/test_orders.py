import pytest
from httpx import AsyncClient
from app.models.menu import MenuItem
from app.models.address import Address
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.order import Order
import datetime

@pytest.mark.asyncio
async def test_place_order_success_returns_placed_status(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem], seeded_address: Address):
    item = seeded_menu_items[0]
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    
    response = await client.post("/api/v1/orders/place", json={
        "delivery_address_id": str(seeded_address.id),
        "payment_method": "COD"
    }, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    if "data" in data:
        data = data["data"]
        
    assert data["status"] == "PLACED"
    assert data["payment_method"] == "COD"
    assert data["total_amount"] >= data["items_total"]

@pytest.mark.asyncio
async def test_place_order_clears_cart_completely(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem], seeded_address: Address):
    item = seeded_menu_items[0]
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    await client.post("/api/v1/orders/place", json={
        "delivery_address_id": str(seeded_address.id),
        "payment_method": "COD"
    }, headers=auth_headers)
    
    cart_response = await client.get("/api/v1/cart", headers=auth_headers)
    cart_data = cart_response.json()
    if "data" in cart_data:
        cart_data = cart_data["data"]
    assert len(cart_data.get("items", [])) == 0

@pytest.mark.asyncio
async def test_place_order_snapshots_item_name_and_price(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem], seeded_address: Address):
    item = seeded_menu_items[0]
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    response = await client.post("/api/v1/orders/place", json={
        "delivery_address_id": str(seeded_address.id),
        "payment_method": "COD"
    }, headers=auth_headers)
    
    data = response.json()
    if "data" in data:
        data = data["data"]
        
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == item.name
    assert float(data["items"][0]["price"]) == float(item.price)

@pytest.mark.asyncio
async def test_place_order_empty_cart_returns_400_cart_empty(client: AsyncClient, auth_headers: dict, seeded_address: Address):
    await client.post("/api/v1/cart/clear", headers=auth_headers)
    response = await client.post("/api/v1/orders/place", json={
        "delivery_address_id": str(seeded_address.id),
        "payment_method": "COD"
    }, headers=auth_headers)
    
    assert response.status_code == 400
    assert response.json().get("error_code") == "CART_EMPTY"

@pytest.mark.asyncio
async def test_place_order_with_coupon_applies_correct_discount(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem], seeded_address: Address, db_session: AsyncSession):
    # Need to seed a coupon first or assume standard one exists? 
    # Usually seed.py creates 2 coupons, let's create one explicitly just in case.
    from app.models.order import Coupon
    coupon = Coupon(code="TEST50", discount_type="FLAT", discount_value=50.0, min_order_amount=100.0, is_active=True, valid_from=datetime.datetime.now(datetime.timezone.utc), valid_until=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
    db_session.add(coupon)
    await db_session.commit()

    item = seeded_menu_items[0]
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    
    response = await client.post("/api/v1/orders/place", json={
        "delivery_address_id": str(seeded_address.id),
        "payment_method": "COD",
        "coupon_code": "TEST50"
    }, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    if "data" in data:
        data = data["data"]
        
    assert float(data["discount_amount"]) == 50.0
    assert data["coupon_code"] == "TEST50"

@pytest.mark.asyncio
async def test_cancel_order_in_placed_status_succeeds(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem], seeded_address: Address):
    item = seeded_menu_items[0]
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    order_resp = await client.post("/api/v1/orders/place", json={
        "delivery_address_id": str(seeded_address.id),
        "payment_method": "COD"
    }, headers=auth_headers)
    order_id = order_resp.json().get("data", order_resp.json())["id"]
    
    response = await client.post(f"/api/v1/orders/{order_id}/cancel", json={"reason": "Changed my mind"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json().get("data", response.json())
    assert data["status"] == "CANCELLED"
    assert data["cancellation_reason"] == "Changed my mind"

@pytest.mark.asyncio
async def test_cancel_order_in_preparing_status_returns_409(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem], seeded_address: Address, db_session: AsyncSession):
    item = seeded_menu_items[0]
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    order_resp = await client.post("/api/v1/orders/place", json={
        "delivery_address_id": str(seeded_address.id),
        "payment_method": "COD"
    }, headers=auth_headers)
    order_id = order_resp.json().get("data", order_resp.json())["id"]
    
    # Manually update order to PREPARING
    order = await db_session.get(Order, order_id)
    order.status = "PREPARING"
    await db_session.commit()
    
    response = await client.post(f"/api/v1/orders/{order_id}/cancel", json={"reason": "Too late"}, headers=auth_headers)
    assert response.status_code == 409
    assert response.json().get("error_code") == "INVALID_STATUS_TRANSITION"

@pytest.mark.asyncio
async def test_invalid_status_transition_returns_409(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem], seeded_address: Address, db_session: AsyncSession):
    item = seeded_menu_items[0]
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    order_resp = await client.post("/api/v1/orders/place", json={
        "delivery_address_id": str(seeded_address.id),
        "payment_method": "COD"
    }, headers=auth_headers)
    order_id = order_resp.json().get("data", order_resp.json())["id"]
    
    # Try to cancel without reason or try to update status backwards if such endpoint exists.
    # We can test the cancel logic returning 409 for invalid transitions.
    # For a general invalid status transition test, let's assume we change status to DELIVERED and try to cancel.
    order = await db_session.get(Order, order_id)
    order.status = "DELIVERED"
    await db_session.commit()
    
    response = await client.post(f"/api/v1/orders/{order_id}/cancel", json={"reason": "Too late"}, headers=auth_headers)
    assert response.status_code == 409
    assert response.json().get("error_code") == "INVALID_STATUS_TRANSITION"
