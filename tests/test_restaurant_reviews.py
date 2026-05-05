from datetime import UTC, datetime

import pytest
import pytest_asyncio

from app.models.order import Order, OrderStatus, PaymentMethod
from app.models.restaurant_partner import BusinessType, RestaurantPartner
from app.models.review import Review
from app.models.user import User
from app.utils.jwt import create_access_token


@pytest_asyncio.fixture
async def review_partner(db_session, seeded_restaurant):
    customer = User(phone="+919111111111", name="Customer Person", is_verified=True)
    partner_user = User(
        phone="+919000000004",
        name="Review Partner",
        is_verified=True,
        role="RESTAURANT_PARTNER",
        restaurant_status="DOCS_APPROVED",
    )
    db_session.add_all([customer, partner_user])
    await db_session.flush()
    partner = RestaurantPartner(
        user_id=partner_user.id,
        restaurant_id=seeded_restaurant.id,
        owner_name="Review Partner",
        business_type=BusinessType.RESTAURANT,
        fssai_number="12345678901234",
    )
    db_session.add(partner)
    order = Order(
        user_id=customer.id,
        restaurant_id=seeded_restaurant.id,
        delivery_address_snapshot={"full_address": "Test"},
        items_total=100,
        delivery_fee=0,
        discount_amount=0,
        total_amount=100,
        payment_method=PaymentMethod.COD,
        status=OrderStatus.DELIVERED,
        delivered_at=datetime.now(UTC),
    )
    db_session.add(order)
    await db_session.flush()
    review = Review(
        order_id=order.id,
        user_id=customer.id,
        restaurant_id=seeded_restaurant.id,
        food_rating=5,
        delivery_rating=4,
        comment="Nice food",
    )
    db_session.add(review)
    await db_session.commit()
    token = create_access_token(
        partner_user.id,
        partner_user.phone,
        role="RESTAURANT_PARTNER",
        restaurant_partner_id=partner.id,
        restaurant_id=seeded_restaurant.id,
    )
    return review, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_reviews_for_restaurant(client, review_partner):
    _, headers = review_partner
    response = await client.get("/api/v1/restaurant/reviews", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["customer_name"] == "Customer"


@pytest.mark.asyncio
async def test_respond_to_review(client, db_session, review_partner):
    review, headers = review_partner
    response = await client.post(
        f"/api/v1/restaurant/reviews/{review.id}/respond",
        json={"response": "Thank you for your feedback!"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["response_text"] == "Thank you for your feedback!"
    await db_session.refresh(review)
    assert review.response_text == "Thank you for your feedback!"


@pytest.mark.asyncio
async def test_respond_too_long(client, review_partner):
    review, headers = review_partner
    response = await client.post(
        f"/api/v1/restaurant/reviews/{review.id}/respond",
        json={"response": "x" * 501},
        headers=headers,
    )
    assert response.status_code == 422
