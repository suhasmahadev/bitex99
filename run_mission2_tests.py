"""
Mission 2 verification script — all 8 tests.
Uses ASGITransport so the server doesn't need to be running separately.
"""
import asyncio
import uuid

from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.database import AsyncSessionLocal
from app.redis_client import init_redis, close_redis


async def get_otp_and_verify(client, redis, phone, register_as_restaurant=False, register_as_partner=False):
    """Send OTP, read it from Redis, then verify it."""
    await client.post("/api/v1/auth/send-otp", json={"phone": phone})
    raw = await redis.get(f"otp:{phone}")
    otp = raw.decode().split(":")[0] if raw else "123456"
    resp = await client.post("/api/v1/auth/verify-otp", json={
        "phone": phone,
        "otp": otp,
        "register_as_restaurant": register_as_restaurant,
        "register_as_partner": register_as_partner
    })
    return resp


async def run_tests():
    await init_redis()
    from app.redis_client import get_redis
    redis = get_redis()

    # Fresh phone numbers so each run is idempotent
    rp_phone = "+918888877777"
    admin_phone = "+911111111111"

    # Clean up previous test data
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM restaurant_timings WHERE restaurant_id IN (SELECT id FROM restaurants WHERE name='Test Kitchen')"))
        await db.execute(text("DELETE FROM restaurant_documents WHERE partner_id IN (SELECT rp.id FROM restaurant_partners rp JOIN restaurants r ON rp.restaurant_id=r.id WHERE r.name='Test Kitchen')"))
        await db.execute(text("DELETE FROM restaurant_partners WHERE restaurant_id IN (SELECT id FROM restaurants WHERE name='Test Kitchen')"))
        await db.execute(text("DELETE FROM restaurants WHERE name='Test Kitchen'"))
        await db.execute(text("DELETE FROM users WHERE phone=:p"), {"p": rp_phone})
        # Ensure admin user exists
        await db.execute(text("INSERT INTO users (phone, is_verified, is_active, role) VALUES (:p, TRUE, TRUE, 'ADMIN') ON CONFLICT (phone) DO UPDATE SET role='ADMIN'"), {"p": admin_phone})
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        # ─── Test 1: Register as restaurant partner ────────────────────────────
        print("\n=== Test 1: Register as restaurant partner ===")
        resp1 = await get_otp_and_verify(client, redis, rp_phone, register_as_restaurant=True)
        d1 = resp1.json()
        if resp1.status_code != 200:
            print("FAIL:", d1)
            return
        print(f"role: {d1['user']['role']}, restaurant_status: {d1['user']['restaurant_status']}, is_new_restaurant_partner: {d1['is_new_restaurant_partner']}")
        token = d1["access_token"]

        # ─── Test 2: Setup restaurant profile ─────────────────────────────────
        print("\n=== Test 2: Setup restaurant profile ===")
        setup_resp = await client.post("/api/v1/restaurant/profile/setup", json={
            "restaurant_name": "Test Kitchen",
            "business_type": "RESTAURANT",
            "cuisine_types": ["Indian", "Chinese"],
            "city": "Mumbai",
            "full_address": "45 Test Road, Andheri West",
            "phone": "+912212345678",
            "owner_name": "Test Owner",
            "fssai_number": "12345678901234",
            "fssai_expiry": "2027-12-31",
            "pan_number": "ABCDE1234F",
            "bank_account_number": "9876543210",
            "bank_ifsc": "HDFC0001234",
            "bank_account_name": "Test Owner",
            "delivery_fee": 30,
            "min_order_amount": 199
        }, headers={"Authorization": f"Bearer {token}"})
        d2 = setup_resp.json()
        if setup_resp.status_code != 200:
            print("FAIL:", d2)
            return
        new_token = d2["new_access_token"]
        partner_id = d2["partner_id"]
        print(f"restaurant_id: {d2['restaurant_id']}, partner_id: {partner_id}, slug: {d2['slug']}")
        print(f"new_access_token: {'OK (present)' if new_token else 'MISSING'}")

        async with AsyncSessionLocal() as db:
            is_open = await db.scalar(text("SELECT is_open FROM restaurants WHERE name='Test Kitchen'"))
        print(f"Restaurant created with is_open: {is_open}")

        # ─── Test 3: Protected route blocked before approval ───────────────────
        print("\n=== Test 3: Protected route blocked before approval ===")
        resp3 = await client.get("/api/v1/restaurant/profile", headers={"Authorization": f"Bearer {new_token}"})
        err3 = resp3.json().get("detail", {})
        print(f"Status: {resp3.status_code}, error_code: {err3.get('error_code', err3)}")

        # ─── Test 4: Upload document ───────────────────────────────────────────
        print("\n=== Test 4: Upload document ===")
        fake_img = b"\xff\xd8\xff" + b"\x00" * 100  # minimal fake JPEG
        files = {"file": ("fssai.jpg", fake_img, "image/jpeg")}
        data = {"doc_type": "FSSAI_LICENSE"}
        resp4 = await client.post("/api/v1/restaurant/documents/upload",
                                  data=data, files=files,
                                  headers={"Authorization": f"Bearer {new_token}"})
        d4 = resp4.json()
        if resp4.status_code != 200:
            print("FAIL:", d4)
        else:
            fssai_doc = next(x for x in d4["documents"] if x["doc_type"] == "FSSAI_LICENSE")
            print(f"FSSAI_LICENSE status: {fssai_doc['status']}, file_url: {fssai_doc['file_url']}")

        # ─── Test 5: Document status shows missing docs ────────────────────────
        print("\n=== Test 5: Check document status shows missing docs ===")
        resp5 = await client.get("/api/v1/restaurant/documents/status",
                                 headers={"Authorization": f"Bearer {new_token}"})
        d5 = resp5.json()
        print(f"missing_required: {len(d5['missing_required'])} remaining - {d5['missing_required']}")
        print(f"can_submit: {d5['can_submit']}")

        # ─── Test 6: Admin approve restaurant ─────────────────────────────────
        print("\n=== Test 6: Admin approve restaurant ===")
        # Upload remaining required docs
        remaining = ["PAN_CARD", "BANK_CANCELLED_CHEQUE", "OWNER_AADHAAR_FRONT", "OWNER_AADHAAR_BACK", "RESTAURANT_PHOTO_FRONT"]
        for doc_type in remaining:
            await client.post("/api/v1/restaurant/documents/upload",
                              data={"doc_type": doc_type},
                              files={"file": (f"{doc_type}.jpg", fake_img, "image/jpeg")},
                              headers={"Authorization": f"Bearer {new_token}"})

        submit_resp = await client.post("/api/v1/restaurant/documents/submit",
                                        headers={"Authorization": f"Bearer {new_token}"})
        print(f"Submit status: {submit_resp.status_code} → {submit_resp.json()['message']}")

        async with AsyncSessionLocal() as db:
            rest_status = await db.scalar(text("SELECT restaurant_status FROM users WHERE phone=:p"), {"p": rp_phone})
        print(f"restaurant_status after submit: {rest_status}")

        # Get admin token
        admin_resp = await get_otp_and_verify(client, redis, admin_phone)
        admin_token = admin_resp.json()["access_token"]

        approve_resp = await client.post(f"/api/v1/admin/restaurant/{partner_id}/approve",
                                          headers={"Authorization": f"Bearer {admin_token}"})
        print(f"Approve response: {approve_resp.status_code} → {approve_resp.json()['message']}")

        async with AsyncSessionLocal() as db:
            is_open_now = await db.scalar(text("SELECT is_open FROM restaurants WHERE name='Test Kitchen'"))
            rest_status_now = await db.scalar(text("SELECT restaurant_status FROM users WHERE phone=:p"), {"p": rp_phone})
        print(f"restaurant_status: {rest_status_now}, is_open: {is_open_now} (should be True)")

        # Verify customer can see it
        cust_resp = await client.get("/api/v1/restaurants?city=Mumbai")
        kitchen = next((r for r in cust_resp.json().get("items", []) if r["name"] == "Test Kitchen"), None)
        print(f"Customer sees Test Kitchen: {'YES, is_open=' + str(kitchen['is_open']) if kitchen else 'NOT FOUND'}")

        # ─── Test 7: Open/close toggle ─────────────────────────────────────────
        print("\n=== Test 7: Open/close toggle with active order check ===")
        resp7 = await client.post("/api/v1/restaurant/profile/open-toggle",
                                   json={"is_open": False},
                                   headers={"Authorization": f"Bearer {new_token}"})
        print(f"Toggle off: {resp7.status_code} → {resp7.json()}")

        cust_resp2 = await client.get("/api/v1/restaurants?city=Mumbai")
        kitchen2 = next((r for r in cust_resp2.json().get("items", []) if r["name"] == "Test Kitchen"), None)
        print(f"Customer sees is_open: {kitchen2['is_open'] if kitchen2 else 'NOT FOUND'}")

        # ─── Test 8: Update timings ─────────────────────────────────────────────
        print("\n=== Test 8: Update timings ===")
        resp8 = await client.patch("/api/v1/restaurant/profile/timings", json=[
            {"day_of_week": 6, "opens_at": "11:00", "closes_at": "22:00", "is_closed": False},
            {"day_of_week": 0, "opens_at": "09:00", "closes_at": "23:30", "is_closed": False}
        ], headers={"Authorization": f"Bearer {new_token}"})
        d8 = resp8.json()
        print(f"Timings returned: {len(d8)} days")
        mon = next((t for t in d8 if t["day_of_week"] == 0), None)
        sun = next((t for t in d8 if t["day_of_week"] == 6), None)
        print(f"Monday: {mon['opens_at']}–{mon['closes_at']}" if mon else "Monday: missing")
        print(f"Sunday: {sun['opens_at']}–{sun['closes_at']}" if sun else "Sunday: missing")

    await close_redis()
    print("\n✅ All 8 tests complete.")


if __name__ == "__main__":
    asyncio.run(run_tests())
