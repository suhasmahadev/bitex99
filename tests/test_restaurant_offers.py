import pytest
import pytest_asyncio

from app.models.restaurant_partner import BusinessType, RestaurantPartner
from app.models.user import User
from app.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def offer_partner(db_session, seeded_restaurant):
    user = User(
        phone="+919000000003",
        name="Offer Partner",
        is_verified=True,
        role="RESTAURANT_PARTNER",
        restaurant_status="DOCS_APPROVED",
    )
    db_session.add(user)
    await db_session.flush()
    partner = RestaurantPartner(
        user_id=user.id,
        restaurant_id=seeded_restaurant.id,
        owner_name="Offer Partner",
        business_type=BusinessType.RESTAURANT,
        fssai_number="12345678901234",
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
    return seeded_restaurant, partner, {"Authorization": f"Bearer {token}"}


def _offer_body():
    return {
        "title": "20% off",
        "offer_type": "PERCENT",
        "discount_value": 20,
        "min_order_amount": 199,
    }


@pytest.mark.asyncio
async def test_create_offer_sets_has_offers_true(client, offer_partner):
    restaurant, _, headers = offer_partner
    response = await client.post("/api/v1/restaurant/offers", json=_offer_body(), headers=headers)
    assert response.status_code == 200

    detail = await client.get(f"/api/v1/restaurants/{restaurant.id}")
    assert detail.status_code == 200
    assert detail.json()["has_offers"] is True


@pytest.mark.asyncio
async def test_toggle_off_last_offer_sets_has_offers_false(client, offer_partner):
    restaurant, _, headers = offer_partner
    created = await client.post("/api/v1/restaurant/offers", json=_offer_body(), headers=headers)
    offer_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/restaurant/offers/{offer_id}/toggle",
        json={"is_active": False},
        headers=headers,
    )
    assert response.status_code == 200
    detail = await client.get(f"/api/v1/restaurants/{restaurant.id}")
    assert detail.json()["has_offers"] is False


@pytest.mark.asyncio
async def test_offer_visible_to_customer_listing(client, offer_partner):
    restaurant, _, headers = offer_partner
    response = await client.post("/api/v1/restaurant/offers", json=_offer_body(), headers=headers)
    assert response.status_code == 200

    listing = await client.get("/api/v1/restaurants?city=Mumbai")
    assert listing.status_code == 200
    data = listing.json()
    match = next(item for item in data["data"] if item["id"] == str(restaurant.id))
    assert match["has_offers"] is True
