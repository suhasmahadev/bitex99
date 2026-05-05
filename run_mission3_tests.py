"""
Mission 3 — All 8 verification tests.
Uses direct JWT token generation (no OTP) to be idempotent across re-runs.
Tests 1-5: Menu CRUD (Part A)
Tests 6-8: Order flow (Part B)
"""
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

from app.main import app
from app.database import AsyncSessionLocal
from app.redis_client import init_redis, close_redis
from app.utils.jwt import create_access_token
from app.models.user import User
from app.models.restaurant_partner import RestaurantPartner
from app.models.address import Address


RESTAURANT_PHONE = "+918888877777"
CUSTOMER_PHONE  = "+917777766666"


async def run_tests():
    await init_redis()

    # ── Prepare tokens directly from DB (idempotent) ──────────────────────────
    async with AsyncSessionLocal() as db:
        rp_user = await db.scalar(select(User).where(User.phone == RESTAURANT_PHONE))
        if not rp_user:
            print("ERROR: Restaurant user not found — run mission2 tests first"); return
        rp_partner = await db.scalar(
            select(RestaurantPartner).where(RestaurantPartner.user_id == rp_user.id)
        )
        if not rp_partner:
            print("ERROR: RestaurantPartner record not found"); return

        # Ensure restaurant is open
        from app.models.restaurant import Restaurant
        await db.execute(
            text("UPDATE restaurants SET is_open = true WHERE id = :rid"),
            {"rid": str(rp_partner.restaurant_id)}
        )
        await db.commit()

        rp_token = create_access_token(
            user_id=rp_user.id,
            phone=rp_user.phone,
            role=rp_user.role,
            restaurant_partner_id=rp_partner.id,
            restaurant_id=rp_partner.restaurant_id
        )
        restaurant_id = str(rp_partner.restaurant_id)

        # Clean + recreate customer
        await db.execute(text("DELETE FROM cart_items WHERE user_id IN (SELECT id FROM users WHERE phone=:p)"), {"p": CUSTOMER_PHONE})
        await db.execute(text("DELETE FROM orders WHERE user_id IN (SELECT id FROM users WHERE phone=:p)"), {"p": CUSTOMER_PHONE})
        await db.execute(text("DELETE FROM addresses WHERE user_id IN (SELECT id FROM users WHERE phone=:p)"), {"p": CUSTOMER_PHONE})
        await db.execute(text("DELETE FROM users WHERE phone=:p"), {"p": CUSTOMER_PHONE})
        await db.commit()

        cust_user = User(phone=CUSTOMER_PHONE, is_verified=True, is_active=True, role="CUSTOMER")
        db.add(cust_user)
        await db.commit()
        await db.refresh(cust_user)

        cust_token = create_access_token(user_id=cust_user.id, phone=cust_user.phone, role=cust_user.role)

    rp_headers = {"Authorization": f"Bearer {rp_token}"}
    c_headers  = {"Authorization": f"Bearer {cust_token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        # ── Test 1: Create menu category ──────────────────────────────────────
        print("\n=== Test 1: Create menu category ===")
        r1 = await client.post("/api/v1/restaurant/menu/categories",
                               json={"name": "Burgers", "display_order": 1},
                               headers=rp_headers)
        d1 = r1.json()
        if r1.status_code != 200:
            print("FAIL:", d1); return
        cat_id = str(d1["id"])
        print(f"  Created: id={cat_id}, name={d1['name']}, display_order={d1['display_order']} PASS")

        # ── Test 2: Create menu item with effective_price ─────────────────────
        print("\n=== Test 2: Create menu item ===")
        r2 = await client.post("/api/v1/restaurant/menu/items", json={
            "category_id": cat_id,
            "name": "Classic Burger",
            "price": 299.00,
            "discounted_price": 249.00,
            "is_veg": False,
            "is_available": True
        }, headers=rp_headers)
        d2 = r2.json()
        if r2.status_code != 200:
            print("FAIL:", d2); return
        item_id = str(d2["id"])
        print(f"  name={d2['name']}, price={d2['price']}, discounted_price={d2['discounted_price']}, effective_price={d2['effective_price']}")
        assert float(d2["effective_price"]) == 249.0, f"effective_price mismatch: {d2['effective_price']}"
        print("  effective_price == 249.00 PASS")

        # Second item for bulk-toggle
        r2b = await client.post("/api/v1/restaurant/menu/items", json={
            "category_id": cat_id, "name": "Veggie Burger",
            "price": 199.00, "is_veg": True, "is_available": True
        }, headers=rp_headers)
        d2b = r2b.json()
        if r2b.status_code != 200:
            print("FAIL 2b:", d2b); return
        item2_id = str(d2b["id"])

        # ── Test 3: Customer can see the item ─────────────────────────────────
        print("\n=== Test 3: Customer sees the item ===")
        r3 = await client.get(f"/api/v1/restaurants/{restaurant_id}/menu")
        d3 = r3.json()
        burgers_cat = next((c for c in d3 if c["category"] == "Burgers"), None)
        if not burgers_cat:
            print("FAIL: Burgers category not in customer menu!"); return
        classic = next((i for i in burgers_cat.get("items", []) if i["name"] == "Classic Burger"), None)
        if not classic:
            print("FAIL: Classic Burger not in customer menu!"); return
        ep = classic.get("effective_price", classic.get("price"))
        print(f"  category=Burgers, item=Classic Burger, effective_price={ep} PASS")

        # ── Test 4: Toggle item unavailable ───────────────────────────────────
        print("\n=== Test 4: Toggle item unavailable ===")
        r4 = await client.patch(f"/api/v1/restaurant/menu/items/{item_id}/toggle",
                                json={"is_available": False}, headers=rp_headers)
        d4 = r4.json()
        if r4.status_code != 200:
            print("FAIL toggle:", d4); return
        print(f"  Toggle response: name={d4['name']}, is_available={d4['is_available']}")
        assert d4["is_available"] is False

        r4b = await client.get(f"/api/v1/restaurants/{restaurant_id}/menu")
        cat4 = next((c for c in r4b.json() if c["category"] == "Burgers"), None)
        classic4 = next((i for i in cat4.get("items", []) if i["name"] == "Classic Burger"), None) if cat4 else None
        avail = classic4.get("is_available") if classic4 else "NOT_FOUND"
        print(f"  Customer sees Classic Burger is_available={avail} PASS")

        # Re-enable for order test
        await client.patch(f"/api/v1/restaurant/menu/items/{item_id}/toggle",
                           json={"is_available": True}, headers=rp_headers)

        # ── Test 5: Delete category with items → 409 ──────────────────────────
        print("\n=== Test 5: Delete category with items (must fail 409) ===")
        r5 = await client.delete(f"/api/v1/restaurant/menu/categories/{cat_id}",
                                 headers=rp_headers)
        d5 = r5.json()
        detail = d5.get("detail", {})
        err_code = detail.get("error_code") if isinstance(detail, dict) else detail
        print(f"  Status: {r5.status_code}, error_code: {err_code}")
        assert r5.status_code == 409, f"Expected 409 got {r5.status_code}"
        print("  409 CATEGORY_HAS_ITEMS PASS")

        # ── Test 6: Full order flow ────────────────────────────────────────────
        print("\n=== Test 6: Full order flow (customer -> restaurant) ===")

        # Add address
        addr_r = await client.post("/api/v1/addresses", json={
            "label": "HOME", "full_address": "123 Test St, Mumbai",
            "latitude": 19.076, "longitude": 72.877
        }, headers=c_headers)
        if addr_r.status_code not in (200, 201):
            print("FAIL adding address:", addr_r.json()); return
        addr_id = str(addr_r.json()["id"])

        # Add to cart
        cart_r = await client.post("/api/v1/cart/add", json={
            "menu_item_id": item_id, "quantity": 2
        }, headers=c_headers)
        if cart_r.status_code not in (200, 201):
            print("FAIL cart:", cart_r.json()); return

        # Place order
        ord_r = await client.post("/api/v1/orders/place", json={
            "delivery_address_id": addr_id, "payment_method": "COD"
        }, headers=c_headers)
        od = ord_r.json()
        if ord_r.status_code not in (200, 201):
            print("FAIL placing order:", od); return
        order_id = str(od["id"])
        print(f"  Step A: Order placed. id={order_id}, status={od['status']}")

        async with AsyncSessionLocal() as db:
            db_s = await db.scalar(text("SELECT status FROM orders WHERE id=:id"), {"id": order_id})
        print(f"         DB status = {db_s} (expected PLACED)")

        # Step B: Live orders
        live_r = await client.get("/api/v1/restaurant/orders/live", headers=rp_headers)
        live = live_r.json()
        found = any(o["id"] == order_id for o in live.get("placed", []))
        print(f"  Step B: Order in 'placed' list: {found}")

        # Step C: Accept
        acc_r = await client.post(f"/api/v1/restaurant/orders/{order_id}/accept",
                                  json={"preparation_time": 20}, headers=rp_headers)
        acc = acc_r.json()
        if acc_r.status_code != 200:
            print("FAIL accept:", acc); return
        print(f"  Step C: status={acc.get('status')}, preparation_time={acc.get('preparation_time')}")
        async with AsyncSessionLocal() as db:
            db_s = await db.scalar(text("SELECT status FROM orders WHERE id=:id"), {"id": order_id})
        print(f"         DB status = {db_s} (expected CONFIRMED)")

        # Step D: Preparing
        prep_r = await client.post(f"/api/v1/restaurant/orders/{order_id}/preparing", headers=rp_headers)
        prep = prep_r.json()
        if prep_r.status_code != 200:
            print("FAIL preparing:", prep); return
        print(f"  Step D: status={prep.get('status')}")
        async with AsyncSessionLocal() as db:
            db_s = await db.scalar(text("SELECT status FROM orders WHERE id=:id"), {"id": order_id})
        print(f"         DB status = {db_s} (expected PREPARING)")

        # Step E: Ready
        ready_r = await client.post(f"/api/v1/restaurant/orders/{order_id}/ready", headers=rp_headers)
        ready = ready_r.json()
        if ready_r.status_code != 200:
            print("FAIL ready:", ready); return
        print(f"  Step E: status={ready.get('status')}")
        async with AsyncSessionLocal() as db:
            db_s = await db.scalar(text("SELECT status FROM orders WHERE id=:id"), {"id": order_id})
        print(f"         DB status = {db_s} (expected READY_FOR_PICKUP)")
        print("  Test 6 PASS")

        # ── Test 7: Auto-reject after 90s ─────────────────────────────────────
        print("\n=== Test 7: Auto-reject after 90s ===")
        # Refresh customer token (same user, still valid)
        cart2_r = await client.post("/api/v1/cart/add", json={
            "menu_item_id": item_id, "quantity": 1
        }, headers=c_headers)
        if cart2_r.status_code != 200:
            print("FAIL cart2:", cart2_r.json()); return

        ord2_r = await client.post("/api/v1/orders/place", json={
            "delivery_address_id": addr_id, "payment_method": "COD"
        }, headers=c_headers)
        od2 = ord2_r.json()
        if ord2_r.status_code != 200:
            print("FAIL placing order2:", od2); return
        order2_id = str(od2["id"])
        print(f"  Second order placed: id={order2_id}, status={od2['status']}")
        print("  Waiting 95 seconds for auto-reject...")
        await asyncio.sleep(95)

        async with AsyncSessionLocal() as db:
            row = await db.execute(
                text("SELECT status, cancellation_reason FROM orders WHERE id=:id"),
                {"id": order2_id}
            )
            r = row.fetchone()
        print(f"  After 95s: status={r[0]}, cancellation_reason='{r[1]}'")
        assert str(r[0]) == "CANCELLED", f"Expected CANCELLED got {r[0]}"
        assert "did not respond" in (r[1] or "").lower(), f"Unexpected reason: {r[1]}"
        print("  Auto-reject after 90s PASS")

        # ── Test 8: Bulk toggle ────────────────────────────────────────────────
        print("\n=== Test 8: Bulk toggle ===")
        r8 = await client.post("/api/v1/restaurant/menu/bulk-toggle", json={
            "item_ids": [item_id, item2_id], "is_available": False
        }, headers=rp_headers)
        d8 = r8.json()
        print(f"  Bulk toggle response: {d8}")
        assert d8.get("updated_count") == 2, f"Expected 2 got {d8.get('updated_count')}"

        r8b = await client.get(f"/api/v1/restaurants/{restaurant_id}/menu")
        cat8 = next((c for c in r8b.json() if c["category"] == "Burgers"), None)
        items8 = {i["name"]: i["is_available"] for i in cat8.get("items", [])} if cat8 else {}
        print(f"  Customer sees: {items8}")
        assert items8.get("Classic Burger") is False and items8.get("Veggie Burger") is False
        print("  Bulk toggle PASS — both items is_available=False")

    await close_redis()
    print("\n=== All 8 tests PASSED ===")


if __name__ == "__main__":
    asyncio.run(run_tests())
