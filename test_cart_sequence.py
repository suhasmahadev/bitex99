"""
Cart integration test: 8 sequential tests against the live server.
Authenticates via OTP, seeds data, then exercises all cart rules.
"""
import asyncio
import json
import sys

import httpx
import redis.asyncio as aioredis

BASE = "http://localhost:8000"
PHONE = "+919999900001"


async def get_token() -> str:
    """Authenticate via OTP and return access_token."""
    r = aioredis.from_url("redis://localhost:6379/0", decode_responses=False)

    async with httpx.AsyncClient(base_url=BASE) as client:
        # Send OTP
        resp = await client.post("/api/v1/auth/send-otp", json={"phone": PHONE})
        assert resp.status_code == 200, f"send-otp failed: {resp.text}"

        # Read OTP from Redis
        raw = await r.get(f"otp:{PHONE}")
        otp = raw.decode().split(":")[0]

        # Verify OTP
        resp = await client.post("/api/v1/auth/verify-otp", json={"phone": PHONE, "otp": otp})
        assert resp.status_code == 200, f"verify-otp failed: {resp.text}"
        token = resp.json()["access_token"]

    await r.aclose()
    return token


async def get_seed_ids():
    """Fetch menu item IDs from 2 different restaurants."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    e = create_async_engine("postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex")
    async with e.connect() as c:
        # Get first restaurant and one of its items
        r1 = await c.execute(text(
            "SELECT r.id, r.name FROM restaurants r ORDER BY r.name LIMIT 1"
        ))
        rest1 = r1.fetchone()

        r1_items = await c.execute(text(
            "SELECT id, name, price, discounted_price FROM menu_items WHERE restaurant_id = :rid LIMIT 1"
        ), {"rid": rest1[0]})
        item1 = r1_items.fetchone()

        # Get second restaurant and one of its items
        r2 = await c.execute(text(
            "SELECT r.id, r.name FROM restaurants r WHERE r.id != :rid ORDER BY r.name LIMIT 1"
        ), {"rid": rest1[0]})
        rest2 = r2.fetchone()

        r2_items = await c.execute(text(
            "SELECT id, name, price, discounted_price FROM menu_items WHERE restaurant_id = :rid LIMIT 1"
        ), {"rid": rest2[0]})
        item2 = r2_items.fetchone()

    await e.dispose()
    return {
        "rest1_id": str(rest1[0]), "rest1_name": rest1[1],
        "item1_id": str(item1[0]), "item1_name": item1[1],
        "item1_price": float(item1[2]), "item1_disc": float(item1[3]) if item1[3] else None,
        "rest2_id": str(rest2[0]), "rest2_name": rest2[1],
        "item2_id": str(item2[0]), "item2_name": item2[1],
    }


def pp(label: str, resp):
    """Pretty-print a response."""
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"Status: {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)
    print(f"{'='*60}")


async def run_tests():
    token = await get_token()
    ids = await get_seed_ids()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print(f"\nUsing Restaurant 1: {ids['rest1_name']} (item: {ids['item1_name']})")
    print(f"Using Restaurant 2: {ids['rest2_name']} (item: {ids['item2_name']})")

    async with httpx.AsyncClient(base_url=BASE, headers=headers) as c:

        # Clear cart first to ensure clean state
        await c.post("/api/v1/cart/clear")

        # ── Test 1: Add item to empty cart ────────────────────────────────
        resp = await c.post("/api/v1/cart/add", json={"menu_item_id": ids["item1_id"]})
        pp("TEST 1 - Add item to empty cart", resp)

        # ── Test 2: Add same item again (quantity increment) ──────────────
        resp = await c.post("/api/v1/cart/add", json={"menu_item_id": ids["item1_id"]})
        pp("TEST 2 - Add same item again (quantity should be 2)", resp)

        # ── Test 3: Get cart ──────────────────────────────────────────────
        resp = await c.get("/api/v1/cart")
        pp("TEST 3 - Get cart (full response with totals)", resp)

        # ── Test 4: Add item from DIFFERENT restaurant (409 conflict) ─────
        resp = await c.post("/api/v1/cart/add", json={"menu_item_id": ids["item2_id"]})
        pp("TEST 4 - Add from different restaurant (expect 409 CART_CONFLICT)", resp)

        # ── Test 5: Update quantity to 3 ──────────────────────────────────
        resp = await c.post("/api/v1/cart/update-quantity",
                            json={"menu_item_id": ids["item1_id"], "quantity": 3})
        pp("TEST 5 - Update quantity to 3", resp)

        # ── Test 6: Update quantity to 0 (remove item) ────────────────────
        resp = await c.post("/api/v1/cart/update-quantity",
                            json={"menu_item_id": ids["item1_id"], "quantity": 0})
        pp("TEST 6 - Update quantity to 0 (remove, expect empty cart)", resp)

        # ── Test 7: Add unavailable item ──────────────────────────────────
        # First mark an item as unavailable directly
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text as sa_text
        e = create_async_engine("postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex",
                                isolation_level="AUTOCOMMIT")
        async with e.connect() as conn:
            await conn.execute(sa_text(
                "UPDATE menu_items SET is_available = false WHERE id = :id"
            ), {"id": ids["item1_id"]})
        await e.dispose()

        resp = await c.post("/api/v1/cart/add", json={"menu_item_id": ids["item1_id"]})
        pp("TEST 7 - Add unavailable item (expect 409 ITEM_UNAVAILABLE)", resp)

        # Restore availability
        e = create_async_engine("postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex",
                                isolation_level="AUTOCOMMIT")
        async with e.connect() as conn:
            await conn.execute(sa_text(
                "UPDATE menu_items SET is_available = true WHERE id = :id"
            ), {"id": ids["item1_id"]})
        await e.dispose()

        # ── Test 8: Clear cart ────────────────────────────────────────────
        # Add a few items first
        await c.post("/api/v1/cart/add", json={"menu_item_id": ids["item1_id"]})
        await c.post("/api/v1/cart/add", json={"menu_item_id": ids["item1_id"], "quantity": 2})

        resp = await c.post("/api/v1/cart/clear")
        pp("TEST 8 - Clear cart", resp)

        # Verify cart is empty
        resp = await c.get("/api/v1/cart")
        pp("TEST 8 (verify) - GET /cart after clear (expect empty)", resp)

    print("\n\nAll 8 tests complete.")


if __name__ == "__main__":
    asyncio.run(run_tests())
