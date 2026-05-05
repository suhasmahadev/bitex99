import asyncio
import json
from uuid import UUID

from fastapi.testclient import TestClient
import fakeredis.aioredis

from app.main import app
from app.dependencies import redis_dep

# Mock redis dependency
fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=False)

async def override_redis_dep():
    return fake_redis

app.dependency_overrides[redis_dep] = override_redis_dep

client = TestClient(app)

async def run_sequence():
    print("--- 1. Send OTP ---")
    response = client.post(
        "/api/v1/auth/send-otp",
        json={"phone": "+911234567890"}
    )
    print("curl output:", response.json())

    print("\n--- 2. Check Redis directly ---")
    otp_key = "otp:+911234567890"
    otp_val = await fake_redis.get(otp_key)
    print(f"redis-cli GET '{otp_key}' ->", otp_val.decode() if otp_val else "(nil)")

    print("\n--- 3. Check cooldown key ---")
    cooldown_key = "otp:cooldown:+911234567890"
    cd_val = await fake_redis.get(cooldown_key)
    print(f"redis-cli GET '{cooldown_key}' ->", cd_val.decode() if cd_val else "(nil)")

    print("\n--- 4. Verify OTP ---")
    actual_otp = otp_val.decode().split(":")[0]
    response2 = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": "+911234567890", "otp": actual_otp}
    )
    # Filter out long tokens for readable output
    resp_json = response2.json()
    if "access_token" in resp_json:
        resp_json["access_token"] = "<token>"
        resp_json["refresh_token"] = "<token>"
    print("curl output:", json.dumps(resp_json, indent=2))

    print("\n--- 5. Verify OTP key is deleted ---")
    otp_val2 = await fake_redis.get(otp_key)
    print(f"redis-cli GET '{otp_key}' ->", otp_val2.decode() if otp_val2 else "(nil)")

    print("\n--- 6. Test cooldown ---")
    response3 = client.post(
        "/api/v1/auth/send-otp",
        json={"phone": "+911234567890"}
    )
    print("curl output:", response3.json())

    print("\n--- 7. Test wrong OTP 3 times ---")
    # Clear cooldown to send fresh OTP
    await fake_redis.delete(cooldown_key)
    client.post("/api/v1/auth/send-otp", json={"phone": "+911234567890"})
    
    # 3 failures
    for i in range(1, 4):
        resp = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+911234567890", "otp": "999999"}
        )
        print(f"Attempt {i} output:", resp.json())

    # Check key is deleted
    final_val = await fake_redis.get(otp_key)
    print(f"redis-cli GET '{otp_key}' after lockout ->", final_val.decode() if final_val else "(nil)")

if __name__ == "__main__":
    asyncio.run(run_sequence())
