from datetime import UTC, datetime

import pytest
import pytest_asyncio

from app.models.order import Order, OrderStatus, PaymentMethod
from app.models.restaurant_partner import BusinessType, RestaurantPartner
from app.models.user import User
from app.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def payout_partner(db_session, seeded_restaurant):
    user = User(
        phone="+919000000002",
        name="Payout Partner",
        is_verified=True,
        role="RESTAURANT_PARTNER",
        restaurant_status="DOCS_APPROVED",
    )
    db_session.add(user)
    await db_session.flush()
    partner = RestaurantPartner(
        user_id=user.id,
        restaurant_id=seeded_restaurant.id,
        owner_name="Payout Partner",
        business_type=BusinessType.RESTAURANT,
        fssai_number="12345678901234",
        bank_account_number="1234567890",
        wallet_balance=500,
        commission_rate=20,
    )
    db_session.add(partner)
    await db_session.commit()
    token = create_access_token(
        user.id,
        user.phone,
        role="RESTAURANT_PARTNER",
        restaurant_partner_id=partner.id,
        restaurant_id=seeded_restaurant.id,
    )
    return partner, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_pending_payout_matches_wallet_balance(client, payout_partner):
    partner, headers = payout_partner
    response = await client.get("/api/v1/restaurant/payouts/pending", headers=headers)
    assert response.status_code == 200
    assert response.json()["pending_amount"] == float(partner.wallet_balance)


@pytest.mark.asyncio
async def test_payout_request_success(client, db_session, payout_partner):
    partner, headers = payout_partner
    response = await client.post("/api/v1/restaurant/payouts/request", json={"amount": 100}, headers=headers)
    assert response.status_code == 200
    assert response.json()["utr_number"]
    await db_session.refresh(partner)
    assert float(partner.wallet_balance) == 400.0


@pytest.mark.asyncio
async def test_payout_insufficient_balance(client, payout_partner):
    _, headers = payout_partner
    response = await client.post("/api/v1/restaurant/payouts/request", json={"amount": 999999}, headers=headers)
    assert response.status_code == 402
    assert response.json()["detail"]["error_code"] == "INSUFFICIENT_BALANCE"


@pytest.mark.asyncio
async def test_payout_below_minimum(client, payout_partner):
    _, headers = payout_partner
    response = await client.post("/api/v1/restaurant/payouts/request", json={"amount": 50}, headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "MIN_WITHDRAWAL"
