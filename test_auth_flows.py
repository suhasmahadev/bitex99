import asyncio
import httpx
import json
import redis.asyncio as aioredis

BASE_URL = "http://localhost:8000/api/v1"
REDIS_URL = "redis://localhost:6379/0"

async def get_otp_from_redis(phone: str) -> str:
    redis = await aioredis.from_url(REDIS_URL)
    key = f"otp:{phone}"
    otp = await redis.get(key)
    await redis.aclose()
    if otp:
        return otp.decode("utf-8")
    return "000000"

async def test_flow(role: str, phone: str, name: str):
    print(f"\n{'='*50}\nTesting Flow: {role}\n{'='*50}")
    async with httpx.AsyncClient() as client:
        # Step 1: Send OTP
        print(f"Step 1: Send OTP to {phone}")
        res = await client.post(f"{BASE_URL}/auth/send-otp", json={"phone": phone})
        print(f"Send OTP Response ({res.status_code}):", json.dumps(res.json(), indent=2))
        
        # Step 2: Get OTP from Redis
        await asyncio.sleep(0.5)
        otp = await get_otp_from_redis(phone)
        print(f"OTP retrieved from Redis: {otp}")
        
        # Step 3: Verify OTP
        print(f"\nStep 3: Verify OTP (register_as_partner={role == 'DELIVERY_PARTNER'})")
        verify_payload = {
            "phone": phone,
            "otp": otp,
            "register_as_partner": role == "DELIVERY_PARTNER"
        }
        res = await client.post(f"{BASE_URL}/auth/verify-otp", json=verify_payload)
        verify_data = res.json()
        print(f"Verify OTP Response ({res.status_code}):", json.dumps(verify_data, indent=2))
        
        if res.status_code == 200:
            token = verify_data["data"]["access_token"]
            is_new_user = verify_data["data"]["is_new_user"]
            
            # Step 4: Update name if new user
            if is_new_user:
                print(f"\nStep 4: Update Name to '{name}'")
                headers = {"Authorization": f"Bearer {token}"}
                res = await client.patch(f"{BASE_URL}/users/me", json={"name": name}, headers=headers)
                print(f"Update Name Response ({res.status_code}):", json.dumps(res.json(), indent=2))
            else:
                print(f"\nStep 4: Existing user, skipping name update.")

async def main():
    # Customer flow
    await test_flow("CUSTOMER", "+919876543210", "Rahul")
    
    # Delivery Partner flow
    await test_flow("DELIVERY_PARTNER", "+919999988888", "Siddharth")

if __name__ == "__main__":
    asyncio.run(main())
