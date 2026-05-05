import pytest
from httpx import AsyncClient
import fakeredis
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User

@pytest.mark.asyncio
async def test_send_otp_success(client: AsyncClient, redis_client_fixture: fakeredis.FakeAsyncRedis):
    response = await client.post("/api/v1/auth/send-otp", json={"phone": "+919876543210"})
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "OTP sent"
    assert "expires_in" in data

@pytest.mark.asyncio
async def test_send_otp_cooldown_returns_429_with_seconds_remaining(client: AsyncClient, redis_client_fixture: fakeredis.FakeAsyncRedis):
    # First request
    await client.post("/api/v1/auth/send-otp", json={"phone": "+919876543210"})
    # Second request immediately
    response2 = await client.post("/api/v1/auth/send-otp", json={"phone": "+919876543210"})
    assert response2.status_code == 429
    data = response2.json()
    details = data.get("details", data)
    assert "seconds_remaining" in details
    assert data["error_code"] == "OTP_COOLDOWN"

@pytest.mark.asyncio
async def test_verify_otp_success_new_user_returns_is_new_user_true(client: AsyncClient, redis_client_fixture: fakeredis.FakeAsyncRedis):
    phone = "+919876543211"
    await redis_client_fixture.set(f"otp:{phone}", "123456:0")
    response = await client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "123456"})
    assert response.status_code == 200
    data = response.json()
    # It might return enveloped like {"success": true, "data": {...}} or flat. Let's assume enveloped since spec says standard envelope on ALL endpoints.
    if "data" in data:
        data = data["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["is_new_user"] is True

@pytest.mark.asyncio
async def test_verify_otp_existing_user_returns_is_new_user_false(client: AsyncClient, redis_client_fixture: fakeredis.FakeAsyncRedis, test_user: User):
    phone = test_user.phone
    await redis_client_fixture.set(f"otp:{phone}", "123456:0")
    response = await client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "123456"})
    assert response.status_code == 200
    data = response.json()
    if "data" in data:
        data = data["data"]
    assert data["is_new_user"] is False

@pytest.mark.asyncio
async def test_verify_otp_wrong_code_decrements_attempts_remaining(client: AsyncClient, redis_client_fixture: fakeredis.FakeAsyncRedis):
    phone = "+919876543212"
    await redis_client_fixture.set(f"otp:{phone}", "123456:0")
    response = await client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "000000"})
    assert response.status_code == 401
    data = response.json()
    if "details" in data:
        assert data["details"]["attempts_remaining"] == 2
    else:
        assert data["attempts_remaining"] == 2

@pytest.mark.asyncio
async def test_verify_otp_three_failures_returns_429_and_deletes_key(client: AsyncClient, redis_client_fixture: fakeredis.FakeAsyncRedis):
    phone = "+919876543213"
    await redis_client_fixture.set(f"otp:{phone}", "123456:2") # 2 failures already
    response = await client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "000000"})
    assert response.status_code == 429
    data = response.json()
    assert data["error_code"] == "TOO_MANY_OTP_ATTEMPTS"
    assert not await redis_client_fixture.exists(f"otp:{phone}")

@pytest.mark.asyncio
async def test_verify_otp_expired_key_returns_401(client: AsyncClient, redis_client_fixture: fakeredis.FakeAsyncRedis):
    phone = "+919876543214"
    # No OTP in redis
    response = await client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "123456"})
    assert response.status_code == 401
    data = response.json()
    assert data["error_code"] == "OTP_EXPIRED"

@pytest.mark.asyncio
async def test_refresh_token_rotation_invalidates_old_token(client: AsyncClient, redis_client_fixture: fakeredis.FakeAsyncRedis, test_user: User):
    # Verify OTP to get valid refresh token
    phone = test_user.phone
    await redis_client_fixture.set(f"otp:{phone}", "123456:0")
    login_resp = await client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "123456"})
    data = login_resp.json()
    if "data" in data:
        data = data["data"]
    refresh_token = data["refresh_token"]

    # First refresh
    refresh_resp1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp1.status_code == 200
    
    # Second refresh with same token should fail
    refresh_resp2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp2.status_code == 401
    assert refresh_resp2.json()["error_code"] in ["TOKEN_INVALID", "AUTH_REQUIRED", "TOKEN_EXPIRED", "INVALID_CREDENTIALS"]

@pytest.mark.asyncio
async def test_logout_deletes_refresh_token_from_redis(client: AsyncClient, redis_client_fixture: fakeredis.FakeAsyncRedis, auth_headers: dict, test_user: User):
    # First set a dummy refresh token
    await redis_client_fixture.set(f"refresh:{test_user.id}", "dummy_hash")
    
    response = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    
    # Check it's deleted
    assert not await redis_client_fixture.exists(f"refresh:{test_user.id}")
