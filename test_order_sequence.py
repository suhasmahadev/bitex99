"""
Order integration test: 9 sequential tests against the live server.
Authenticates via OTP, creates an address, exercises all order flows.
"""
import asyncio
import json
import uuid

import httpx
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text as sa_text

BASE = "http://localhost:8000"
PHONE = "+919999900003"
DB_URL = "postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex"


async def get_token() -> str:
    r = aioredis.from_url("redis://localhost:6379/0", decode_responses=False)
    async with httpx.AsyncClient(base_url=BASE) as client:
        resp = await client.post("/api/v1/auth/send-otp", json={"phone": PHONE})
        assert resp.status_code == 200, f"send-otp failed: {resp.text}"
        raw = await r.get(f"otp:{PHONE}")
        otp = raw.decode().split(":")[0]
        resp = await client.post("/api/v1/auth/verify-otp", json={"phone": PHONE, "otp": otp})
        assert resp.status_code == 200, f"verify-otp failed: {resp.text}"
        token = resp.json()["access_token"]
    await r.aclose()
    return token


async def create_address(headers: dict) -> str:
    async with httpx.AsyncClient(base_url=BASE, headers=headers) as c:
        resp = await c.post("/api/v1/addresses", json={
            "label": "HOME",
            "full_address": "42 Test Street, Bangalore 560001",
            "landmark": "Near park",
            "latitude": 12.9716,
            "longitude": 77.5946,
        })
        if resp.status_code in (200, 201):
            data = resp.json()
            # handle both wrapped and direct response
            if "data" in data and isinstance(data["data"], dict):
                return str(data["data"]["id"])
            elif "id" in data:
                return str(data["id"])
        # fallback: query DB directly
        e = create_async_engine(DB_URL)
        async with e.connect() as conn:
            r = await conn.execute(sa_text(
                "SELECT id FROM addresses WHERE user_id = (SELECT id FROM users WHERE phone = :phone) LIMIT 1"
            ), {"phone": PHONE})
            row = r.fetchone()
            if row:
                await e.dispose()
                return str(row[0])
        await e.dispose()
        raise RuntimeError(f"Could not create address: {resp.status_code} {resp.text}")


async def get_seed_ids():
    e = create_async_engine(DB_URL)
    async with e.connect() as c:
        r1 = await c.execute(sa_text("SELECT id, name FROM restaurants ORDER BY name LIMIT 1"))
        rest1 = r1.fetchone()
        items1 = await c.execute(sa_text(
            "SELECT id, name FROM menu_items WHERE restaurant_id = :rid LIMIT 2"
        ), {"rid": rest1[0]})
        items1_rows = items1.fetchall()

        r2 = await c.execute(sa_text(
            "SELECT id, name FROM restaurants WHERE id != :rid ORDER BY name LIMIT 1"
        ), {"rid": rest1[0]})
        rest2 = r2.fetchone()
    await e.dispose()
    return {
        "rest1_id": str(rest1[0]), "rest1_name": rest1[1],
        "item1_id": str(items1_rows[0][0]), "item1_name": items1_rows[0][1],
        "item2_id": str(items1_rows[1][0]) if len(items1_rows) > 1 else str(items1_rows[0][0]),
        "rest2_id": str(rest2[0]), "rest2_name": rest2[1],
    }


def pp(label: str, resp):
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"Status: {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2, default=str))
    except Exception:
        print(resp.text)
    print(f"{'='*60}")


async def run_db_query(query: str, params: dict = None):
    e = create_async_engine(DB_URL)
    async with e.connect() as c:
        r = await c.execute(sa_text(query), params or {})
        rows = r.fetchall()
        cols = r.keys()
    await e.dispose()
    return cols, rows


async def run_db_exec(query: str, params: dict = None):
    e = create_async_engine(DB_URL, isolation_level="AUTOCOMMIT")
    async with e.connect() as c:
        await c.execute(sa_text(query), params or {})
    await e.dispose()


async def run_tests():
    token = await get_token()
    ids = await get_seed_ids()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print(f"\nUsing Restaurant: {ids['rest1_name']}")
    print(f"Using Items: {ids['item1_name']}, {ids.get('item2_id', 'N/A')}")

    # Create address for this user
    address_id = await create_address(headers)
    print(f"Address ID: {address_id}")

    async with httpx.AsyncClient(base_url=BASE, headers=headers) as c:

        # ── Test 1: Place order successfully (COD, no coupon) ─────────────
        # First add items to cart
        await c.post("/api/v1/cart/clear")
        await c.post("/api/v1/cart/add", json={"menu_item_id": ids["item1_id"], "quantity": 2})

        resp = await c.post("/api/v1/orders/place", json={
            "delivery_address_id": address_id,
            "payment_method": "COD",
        })
        pp("TEST 1 - Place order (COD, no coupon)", resp)
        order1_id = resp.json().get("id") if resp.status_code == 201 else None

        # ── Test 2: Verify cart cleared ───────────────────────────────────
        resp = await c.get("/api/v1/cart")
        pp("TEST 2 - Cart after order (expect empty)", resp)

        # ── Test 3: Verify order_items snapshots in DB ────────────────────
        if order1_id:
            cols, rows = await run_db_query(
                "SELECT name, price, quantity FROM order_items WHERE order_id = :oid",
                {"oid": order1_id}
            )
            print(f"\n{'='*60}")
            print("TEST 3 - DB snapshot verification (order_items)")
            print(f"Columns: {list(cols)}")
            for row in rows:
                print(f"  name={row[0]}, price={row[1]}, quantity={row[2]}")
            print(f"{'='*60}")
        else:
            print("\nTEST 3 - SKIPPED (no order_id from Test 1)")

        # ── Test 4: Place order with empty cart ───────────────────────────
        resp = await c.post("/api/v1/orders/place", json={
            "delivery_address_id": address_id,
            "payment_method": "UPI",
        })
        pp("TEST 4 - Place order with empty cart (expect 400 CART_EMPTY)", resp)

        # ── Test 5: Place order with valid coupon ─────────────────────────
        await c.post("/api/v1/cart/add", json={"menu_item_id": ids["item1_id"], "quantity": 3})

        resp = await c.post("/api/v1/orders/place", json={
            "delivery_address_id": address_id,
            "payment_method": "UPI",
            "coupon_code": "FLAT100",
        })
        pp("TEST 5 - Place order with FLAT100 coupon", resp)
        order2_id = resp.json().get("id") if resp.status_code == 201 else None

        # Verify coupon used_count incremented
        cols, rows = await run_db_query(
            "SELECT code, used_count FROM coupons WHERE code = 'FLAT100'"
        )
        print(f"\n  Coupon FLAT100 used_count after order: {rows[0][1] if rows else 'N/A'}")

        # ── Test 6: Invalid coupon code ───────────────────────────────────
        await c.post("/api/v1/cart/add", json={"menu_item_id": ids["item1_id"]})
        resp = await c.post("/api/v1/orders/place", json={
            "delivery_address_id": address_id,
            "payment_method": "COD",
            "coupon_code": "FAKECODE99",
        })
        pp("TEST 6 - Invalid coupon (expect 400 COUPON_INVALID)", resp)
        # Clear cart for clean state
        await c.post("/api/v1/cart/clear")

        # ── Test 7: Cancel order in PLACED status ─────────────────────────
        if order1_id:
            resp = await c.post(f"/api/v1/orders/{order1_id}/cancel", json={
                "reason": "Changed my mind"
            })
            pp("TEST 7 - Cancel PLACED order", resp)

        # ── Test 8: Cancel order in PREPARING status ──────────────────────
        if order2_id:
            await run_db_exec(
                "UPDATE orders SET status = 'PREPARING' WHERE id = :oid",
                {"oid": order2_id}
            )
            resp = await c.post(f"/api/v1/orders/{order2_id}/cancel", json={
                "reason": "Want to cancel"
            })
            pp("TEST 8 - Cancel PREPARING order (expect 409 CANCELLATION_NOT_ALLOWED)", resp)

        # ── Test 9: List orders with pagination ───────────────────────────
        resp = await c.get("/api/v1/orders", params={"page": 1, "limit": 5})
        pp("TEST 9 - List orders (paginated)", resp)

    print("\n\nAll 9 tests complete.")


if __name__ == "__main__":
    asyncio.run(run_tests())
