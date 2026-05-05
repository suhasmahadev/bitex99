"""
Mission 8 integration test: 7 sequential tests.
Reviews, Coupons, Rate-limiting, X-Request-ID, Security headers.
"""
import asyncio
import json
import time

import httpx
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text as sa_text

BASE = "http://localhost:8000"
PHONE = "+919999900099"
DB_URL = "postgresql+asyncpg://postgres:1234567890@localhost:5432/bitex"


async def get_token(phone=PHONE) -> str:
    r = aioredis.from_url("redis://localhost:6379/0", decode_responses=False)
    async with httpx.AsyncClient(base_url=BASE) as client:
        resp = await client.post("/api/v1/auth/send-otp", json={"phone": phone})
        assert resp.status_code == 200, f"send-otp failed: {resp.text}"
        raw = await r.get(f"otp:{phone}")
        otp = raw.decode().split(":")[0]
        resp = await client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": otp})
        assert resp.status_code == 200, f"verify-otp failed: {resp.text}"
        token = resp.json()["access_token"]
    await r.aclose()
    return token


async def run_db_exec(query: str, params: dict = None):
    e = create_async_engine(DB_URL, isolation_level="AUTOCOMMIT")
    async with e.connect() as c:
        await c.execute(sa_text(query), params or {})
    await e.dispose()


async def run_db_query(query: str, params: dict = None):
    e = create_async_engine(DB_URL)
    async with e.connect() as c:
        r = await c.execute(sa_text(query), params or {})
        rows = r.fetchall()
        keys = list(r.keys())
    await e.dispose()
    return keys, rows


def pp(label: str, resp, show_headers=False):
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"Status: {resp.status_code}")
    if show_headers:
        for k, v in resp.headers.items():
            if k.lower().startswith("x-") or k.lower() == "retry-after":
                print(f"  {k}: {v}")
    try:
        print(json.dumps(resp.json(), indent=2, default=str))
    except Exception:
        print(resp.text[:500])
    print(f"{'='*60}")


async def run_tests():
    # Clear rate limit keys for localhost from prior runs to avoid blocking get_token
    r = aioredis.from_url("redis://localhost:6379/0")
    keys = await r.keys("ratelimit:*")
    if keys:
        await r.delete(*keys)
    await r.aclose()

    token = await get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Get orders and the owning user's phone so we can authenticate as them
    _, orders = await run_db_query(
        """SELECT o.id, o.restaurant_id, o.status, u.phone
           FROM orders o JOIN users u ON u.id = o.user_id
           ORDER BY o.created_at DESC LIMIT 5"""
    )
    if not orders:
        print("No orders found -- run test_order_sequence.py first!")
        return

    # Use the owning user's token for review tests
    owner_phone = orders[0][3]
    owner_token = await get_token(owner_phone)
    owner_headers = {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}

    order_id = str(orders[0][0])
    restaurant_id = str(orders[0][1])

    # Pick a different order for non-delivered test (PLACED/CANCELLED)
    non_delivered_order = next(
        (str(o[0]) for o in orders if str(o[2]) in ("PLACED", "CANCELLED")), None
    )

    # Set first order to DELIVERED
    await run_db_exec(
        "UPDATE orders SET status = 'DELIVERED' WHERE id = :oid", {"oid": order_id}
    )
    print(f"\nSet order {order_id} -> DELIVERED")
    print(f"Restaurant: {restaurant_id}")

    # Check restaurant rating before
    _, before = await run_db_query(
        "SELECT rating, total_reviews FROM restaurants WHERE id = :rid",
        {"rid": restaurant_id}
    )
    print(f"Restaurant rating BEFORE: {before[0][0]}, total_reviews: {before[0][1]}")

    async with httpx.AsyncClient(base_url=BASE, headers=owner_headers) as c:

        # ── Test 1: Review a delivered order ─────────────────────────────
        resp = await c.post("/api/v1/reviews", json={
            "order_id": order_id,
            "food_rating": 5,
            "delivery_rating": 4,
            "comment": "Amazing burger!",
        })
        pp("TEST 1 - Review a delivered order", resp)

        # Verify restaurant rating updated
        _, after = await run_db_query(
            "SELECT rating, total_reviews FROM restaurants WHERE id = :rid",
            {"rid": restaurant_id}
        )
        print(f"  Restaurant rating AFTER:  {after[0][0]}, total_reviews: {after[0][1]}")

        # ── Test 2: Review same order again ───────────────────────────────
        resp = await c.post("/api/v1/reviews", json={
            "order_id": order_id,
            "food_rating": 3,
            "delivery_rating": 3,
            "comment": "Trying again",
        })
        pp("TEST 2 - Review same order again (expect 409 REVIEW_ALREADY_EXISTS)", resp)

        # ── Test 3: Review non-delivered order ────────────────────────────
        if non_delivered_order:
            resp = await c.post("/api/v1/reviews", json={
                "order_id": non_delivered_order,
                "food_rating": 4,
                "delivery_rating": 4,
                "comment": "Testing",
            })
            pp("TEST 3 - Review non-delivered order (expect 409 ORDER_NOT_DELIVERED)", resp)
        else:
            print("\nTEST 3 - SKIPPED (no PLACED/CANCELLED order found)")

        # ── Test 4: Validate coupon ───────────────────────────────────────
        resp = await c.post("/api/v1/coupons/validate", json={
            "code": "FLAT100",
            "order_amount": 500,
        })
        pp("TEST 4 - Validate FLAT100 coupon (expect discount=100, final=400)", resp)

    # ── Test 5: Rate limit on send-otp (IP-based, 5/10min) ────────────────
    print(f"\n{'='*60}")
    print("TEST 5 - Rate limit: 6 rapid send-otp requests (different phones, same IP)")
    print("(first 5 must succeed; 6th must be 429 RATE_LIMIT_EXCEEDED)")

    # Clear rate limit keys for localhost from prior runs
    r = aioredis.from_url("redis://localhost:6379/0")
    keys = await r.keys("ratelimit:*:api_v1_auth_send_otp:*")
    if keys:
        await r.delete(*keys)
    await r.aclose()

    last_resp = None
    async with httpx.AsyncClient(base_url=BASE) as c:
        for i in range(1, 7):
            # Different phone each time to avoid per-phone OTP cooldown
            phone = f"+9199998{i:05d}"
            resp = await c.post("/api/v1/auth/send-otp",
                                json={"phone": phone},
                                headers={"Content-Type": "application/json"})
            status_str = f"Request {i} ({phone}): Status {resp.status_code}"
            if resp.status_code == 429 and resp.json().get("error_code") == "RATE_LIMIT_EXCEEDED":
                last_resp = resp
                print(f"  {status_str} <- RATE LIMIT HIT (IP rate limiter)")
                print(f"  Body: {resp.json()}")
                print(f"  Retry-After: {resp.headers.get('Retry-After', 'MISSING')}")
                print(f"  X-Request-ID: {resp.headers.get('x-request-id', 'MISSING')}")
                break
            elif resp.status_code == 429:
                print(f"  {status_str}: other 429 -> {resp.json().get('error_code')}")
            else:
                print(f"  {status_str}: {resp.json().get('message', 'ok')}")
            await asyncio.sleep(0.05)

    if last_resp is None:
        print("  WARNING: IP rate limit was NOT triggered in 6 requests!")
    print(f"{'='*60}")

    # ── Test 6: X-Request-ID on every response ─────────────────────────────
    async with httpx.AsyncClient(base_url=BASE) as c:
        r1 = await c.get("/api/v1/health")
        r2 = await c.get("/api/v1/health")
        id1 = r1.headers.get("x-request-id", "MISSING")
        id2 = r2.headers.get("x-request-id", "MISSING")

        print(f"\n{'='*60}")
        print("TEST 6 - X-Request-ID on every response")
        print(f"  Request 1 X-Request-ID: {id1}")
        print(f"  Request 2 X-Request-ID: {id2}")
        print(f"  Are they different? {'YES' if id1 != id2 else 'NO — FAIL'}")
        print(f"{'='*60}")

    # ── Test 7: Security headers on all responses ──────────────────────────
    async with httpx.AsyncClient(base_url=BASE) as c:
        resp = await c.get("/api/v1/restaurants", params={"city": "Mumbai"})
        x_cto = resp.headers.get("x-content-type-options", "MISSING")
        x_fo = resp.headers.get("x-frame-options", "MISSING")
        x_rid = resp.headers.get("x-request-id", "MISSING")

        print(f"\n{'='*60}")
        print("TEST 7 - Security headers on /api/v1/restaurants")
        print(f"  X-Content-Type-Options: {x_cto}")
        print(f"  X-Frame-Options: {x_fo}")
        print(f"  X-Request-ID: {x_rid}")
        print(f"  Status: {resp.status_code}")
        print(f"{'='*60}")

    print("\n\nAll 7 tests complete.")


if __name__ == "__main__":
    asyncio.run(run_tests())
