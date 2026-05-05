import pytest
from httpx import AsyncClient
from app.models.menu import MenuItem
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.restaurant import Restaurant

@pytest.mark.asyncio
async def test_add_item_to_empty_cart_returns_cart_with_totals(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem]):
    item = seeded_menu_items[0]
    response = await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    if "data" in data:
        data = data["data"]
    
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["menu_item_id"] == str(item.id)
    assert data["items"][0]["quantity"] == 1
    assert data["items_total"] == float(item.price)

@pytest.mark.asyncio
async def test_add_same_item_twice_increments_quantity_not_duplicate_row(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem]):
    item = seeded_menu_items[0]
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    response = await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    if "data" in data:
        data = data["data"]
    
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 2
    assert data["items_total"] == float(item.price) * 2

@pytest.mark.asyncio
async def test_add_item_different_restaurant_returns_409_cart_conflict(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem], db_session: AsyncSession):
    item1 = seeded_menu_items[0]
    
    # Create another restaurant and item
    restaurant2 = Restaurant(name="Dosa Darbar", slug="dosa-darbar", city="Mumbai", full_address="456 St", is_open=True)
    db_session.add(restaurant2)
    await db_session.commit()
    await db_session.refresh(restaurant2)
    
    item2 = MenuItem(restaurant_id=restaurant2.id, category_id=item1.category_id, name="Masala Dosa", price=100.0, is_available=True, is_veg=True)
    db_session.add(item2)
    await db_session.commit()
    await db_session.refresh(item2)

    # Add item from first restaurant
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item1.id), "quantity": 1}, headers=auth_headers)
    
    # Add item from second restaurant
    response = await client.post("/api/v1/cart/add", json={"menu_item_id": str(item2.id), "quantity": 1}, headers=auth_headers)
    assert response.status_code == 409
    data = response.json()
    assert data["error_code"] == "CART_CONFLICT"

@pytest.mark.asyncio
async def test_cart_conflict_response_contains_both_restaurant_names(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem], db_session: AsyncSession):
    item1 = seeded_menu_items[0]
    
    restaurant2 = Restaurant(name="Dosa Darbar", slug="dosa-darbar2", city="Mumbai", full_address="456 St", is_open=True)
    db_session.add(restaurant2)
    await db_session.commit()
    await db_session.refresh(restaurant2)
    
    item2 = MenuItem(restaurant_id=restaurant2.id, category_id=item1.category_id, name="Masala Dosa 2", price=100.0, is_available=True, is_veg=True)
    db_session.add(item2)
    await db_session.commit()
    await db_session.refresh(item2)

    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item1.id), "quantity": 1}, headers=auth_headers)
    response = await client.post("/api/v1/cart/add", json={"menu_item_id": str(item2.id), "quantity": 1}, headers=auth_headers)
    
    data = response.json()
    details = data.get("details", data)
    assert "existing_restaurant" in details
    assert "new_restaurant" in details
    assert details["existing_restaurant"]["name"] == "Burger Barn"
    assert details["new_restaurant"]["name"] == "Dosa Darbar"

@pytest.mark.asyncio
async def test_update_quantity_to_zero_removes_item(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem]):
    item = seeded_menu_items[0]
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    response = await client.post("/api/v1/cart/update-quantity", json={"menu_item_id": str(item.id), "quantity": 0}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    if "data" in data:
        data = data["data"]
    
    assert len(data["items"]) == 0
    assert data["items_total"] == 0

@pytest.mark.asyncio
async def test_clear_cart_returns_empty_cart(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem]):
    item = seeded_menu_items[0]
    await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 2}, headers=auth_headers)
    response = await client.post("/api/v1/cart/clear", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    if "data" in data:
        data = data["data"]
    
    assert len(data.get("items", [])) == 0

@pytest.mark.asyncio
async def test_add_unavailable_item_returns_409_item_unavailable(client: AsyncClient, auth_headers: dict, seeded_menu_items: list[MenuItem], db_session: AsyncSession):
    item = seeded_menu_items[0]
    item.is_available = False
    db_session.add(item)
    await db_session.commit()
    
    response = await client.post("/api/v1/cart/add", json={"menu_item_id": str(item.id), "quantity": 1}, headers=auth_headers)
    assert response.status_code in [404, 409]
    assert response.json().get("error_code") in ["ITEM_UNAVAILABLE", "NOT_FOUND"]
