import asyncio
import uuid
from datetime import UTC, datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.delivery_partner import DeliveryPartner
from app.utils.jwt import create_access_token
from app.redis_client import init_redis, close_redis

async def run_tests():
    await init_redis()
    try:
        async with AsyncSessionLocal() as db:
            test_phone = f"+91{uuid.uuid4().int % 10000000000:010d}"
            # 1. Setup a test partner
            user = User(
                phone=test_phone,
                name="Test Partner",
                role="DELIVERY_PARTNER",
                partner_status="KYC_APPROVED",
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            partner = DeliveryPartner(
                user_id=user.id,
                fe_id=f"ZFE{uuid.uuid4().int % 100000:05d}",
                city="Mumbai",
                is_online=True,
                wallet_balance=0.0
            )
            db.add(partner)
            await db.commit()
            await db.refresh(partner)

            token = create_access_token(
                user_id=user.id,
                phone=user.phone,
                role=user.role,
                partner_id=partner.id
            )

        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            print("=== TEST 1: Location update HTTP ===")
            res1 = await ac.post("/api/v1/partner/location/update", json={
                "latitude": 19.0760,
                "longitude": 72.8777,
                "speed_kmph": 20.5,
                "heading_degrees": 180
            }, headers=headers)
            print("Status:", res1.status_code)
            print("Response:", res1.json())

            print("\n=== TEST 2: Earnings after delivery ===")
            res2 = await ac.get("/api/v1/partner/earnings/today", headers=headers)
            print("Status:", res2.status_code)
            print("Response:", res2.json())

            print("\n=== TEST 3: Incentive progress ===")
            res3 = await ac.get("/api/v1/partner/incentives/active", headers=headers)
            print("Status:", res3.status_code)
            print("Response:", res3.json())

            print("\n=== TEST 4: Payout pending ===")
            res4 = await ac.get("/api/v1/partner/payouts/pending", headers=headers)
            print("Status:", res4.status_code)
            print("Response:", res4.json())

            print("\n=== TEST 5: Payout withdrawal ===")
            # Give wallet balance
            async with AsyncSessionLocal() as db:
                p = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner.id))
                p.wallet_balance = 100.0
                await db.commit()
                
            res5 = await ac.post("/api/v1/partner/payouts/request", json={"amount": 50.0}, headers=headers)
            print("Status:", res5.status_code)
            print("Response:", res5.json())

            print("\n=== TEST 6: Support ticket ===")
            res6 = await ac.post("/api/v1/partner/support/tickets", json={
                "category": "EARNINGS",
                "subject": "Test ticket",
                "description": "Testing support system"
            }, headers=headers)
            print("Status:", res6.status_code)
            print("Response:", res6.json())
            
            res6b = await ac.get("/api/v1/partner/support/tickets", headers=headers)
            print("Status (List):", res6b.status_code)
            print("Response (List):", res6b.json())

        # Test 7: WebSocket
        from fastapi.testclient import TestClient
        client = TestClient(app)
        print("\n=== TEST 7: WS location stream ===")
        try:
            with client.websocket_connect(f"/api/v1/ws/partner/location?token={token}") as websocket:
                connected_msg = websocket.receive_json()
                print("Connected:", connected_msg)
                websocket.send_json({"latitude":19.0761,"longitude":72.8778,"speed_kmph":22})
                recv = websocket.receive_json()
                print("Received:", recv)
        except Exception as e:
            print("WS Error:", e)

    finally:
        await close_redis()

if __name__ == "__main__":
    asyncio.run(run_tests())
