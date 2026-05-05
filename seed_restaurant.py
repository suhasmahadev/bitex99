import asyncio
import os
import uuid
from datetime import UTC, date, datetime, time
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

os.environ["DEBUG"] = "false"
load_dotenv(Path(__file__).resolve().parent / ".env")

from app.database import AsyncSessionLocal
from app.models.delivery_assignment import DeliveryAssignment
from app.models.delivery_otp import DeliveryOtp
from app.models.menu import MenuCategory, MenuItem
from app.models.order import Order, OrderItem
from app.models.order_response import OrderResponse
from app.models.partner_earnings import PartnerEarnings
from app.models.restaurant import Restaurant
from app.models.restaurant_document import DocStatus, DocType, RestaurantDocument
from app.models.restaurant_offer import OfferType, RestaurantOffer
from app.models.restaurant_partner import BusinessType, RestaurantPartner
from app.models.restaurant_payout import RestaurantPayout
from app.models.restaurant_timing import RestaurantTiming
from app.models.review import Review
from app.models.support_ticket import SupportTicket
from app.models.user import User


REQUIRED_DOC_TYPES = [
    DocType.FSSAI_LICENSE,
    DocType.PAN_CARD,
    DocType.BANK_CANCELLED_CHEQUE,
    DocType.OWNER_AADHAAR_FRONT,
    DocType.OWNER_AADHAAR_BACK,
    DocType.RESTAURANT_PHOTO_FRONT,
]


RESTAURANTS = [
    {
        "name": "Burger Barn",
        "slug": "burger-barn",
        "city": "Mumbai",
        "full_address": "123 MG Road, Bandra West, Mumbai",
        "latitude": 19.0596,
        "longitude": 72.8295,
        "phone": "+912212340001",
        "rating": 4.2,
        "total_reviews": 128,
        "avg_delivery_time": 35,
        "min_order_amount": 199,
        "delivery_fee": 30,
        "is_open": True,
        "is_pure_veg": False,
        "partner_phone": "+919000000001",
        "owner_name": "Rahul Sharma",
        "business_type": BusinessType.RESTAURANT,
        "cuisine_types": ["Burgers", "American"],
        "offer": {"title": "20% off", "offer_type": OfferType.PERCENT, "discount_value": 20, "min_order_amount": 199},
        "categories": {
            "Burgers": [
                ("Classic Smash Burger", 299, 249, False, ["Bestseller"]),
                ("Double Patty", 399, None, False, []),
                ("Veggie Burger", 219, None, True, []),
                ("Chicken Crunch Burger", 279, None, False, []),
            ],
            "Sides": [
                ("Fries", 99, None, True, []),
                ("Chicken Wings", 249, None, False, []),
                ("Cheese Poppers", 169, None, True, []),
            ],
            "Drinks": [
                ("Coke", 60, None, True, []),
                ("Cold Coffee", 110, None, True, []),
                ("Chocolate Shake", 140, None, True, []),
            ],
        },
    },
    {
        "name": "Dosa Darbar",
        "slug": "dosa-darbar-mumbai",
        "city": "Mumbai",
        "full_address": "45 Link Road, Andheri West, Mumbai",
        "latitude": 19.1136,
        "longitude": 72.8697,
        "phone": "+912212340002",
        "rating": 4.5,
        "total_reviews": 210,
        "avg_delivery_time": 25,
        "min_order_amount": 150,
        "delivery_fee": 25,
        "is_open": True,
        "is_pure_veg": True,
        "partner_phone": "+919000000002",
        "owner_name": "Meena Iyer",
        "business_type": BusinessType.RESTAURANT,
        "cuisine_types": ["South Indian", "Dosa"],
        "offer": {"title": "Flat 40 off", "offer_type": OfferType.FLAT, "discount_value": 40, "min_order_amount": 199},
        "categories": {
            "Dosas": [
                ("Masala Dosa", 129, 109, True, ["Bestseller"]),
                ("Mysore Masala Dosa", 149, None, True, ["Spicy"]),
                ("Cheese Dosa", 159, None, True, []),
                ("Rava Dosa", 139, None, True, []),
                ("Onion Uttapam", 149, None, True, []),
            ],
            "Idli": [
                ("Idli Sambar", 79, None, True, []),
                ("Mini Idli", 89, None, True, []),
                ("Medu Vada", 89, None, True, []),
            ],
            "Beverages": [
                ("Filter Coffee", 45, None, True, ["Bestseller"]),
                ("Buttermilk", 35, None, True, []),
            ],
        },
    },
    {
        "name": "Tandoor Times",
        "slug": "tandoor-times",
        "city": "Mumbai",
        "full_address": "77 Central Avenue, Powai, Mumbai",
        "latitude": 19.1197,
        "longitude": 72.9051,
        "phone": "+912212340003",
        "rating": 4.3,
        "total_reviews": 165,
        "avg_delivery_time": 50,
        "min_order_amount": 299,
        "delivery_fee": 45,
        "is_open": False,
        "is_pure_veg": False,
        "partner_phone": "+919000000003",
        "owner_name": "Arjun Malhotra",
        "business_type": BusinessType.RESTAURANT,
        "cuisine_types": ["North Indian", "Punjabi"],
        "offer": {"title": "Free delivery", "offer_type": OfferType.FREE_DELIVERY, "discount_value": 0, "min_order_amount": 299},
        "categories": {
            "Dal": [
                ("Dal Tadka", 199, None, True, []),
                ("Dal Makhani", 229, None, True, ["Bestseller"]),
            ],
            "Paneer": [
                ("Paneer Butter Masala", 269, None, True, ["Bestseller"]),
                ("Kadai Paneer", 259, None, True, []),
                ("Paneer Lababdar", 279, None, True, []),
            ],
            "Chicken": [
                ("Butter Chicken", 329, 299, False, ["Bestseller"]),
                ("Kadai Chicken", 319, None, False, []),
                ("Chicken Curry", 289, None, False, []),
            ],
            "Breads": [
                ("Butter Naan", 49, None, True, []),
                ("Garlic Naan", 59, None, True, []),
                ("Tandoori Roti", 35, None, True, []),
            ],
        },
    },
    {
        "name": "Biryani Blues",
        "slug": "biryani-blues",
        "city": "Delhi",
        "full_address": "22 Connaught Place, New Delhi",
        "latitude": 28.6315,
        "longitude": 77.2167,
        "phone": "+911123400004",
        "rating": 4.6,
        "total_reviews": 240,
        "avg_delivery_time": 45,
        "min_order_amount": 299,
        "delivery_fee": 40,
        "is_open": True,
        "is_pure_veg": False,
        "partner_phone": "+919000000004",
        "owner_name": "Sajid Khan",
        "business_type": BusinessType.RESTAURANT,
        "cuisine_types": ["Biryani", "Mughlai"],
        "offer": {"title": "15% off", "offer_type": OfferType.PERCENT, "discount_value": 15, "min_order_amount": 299},
        "categories": {
            "Biryani": [
                ("Chicken Dum Biryani", 329, 289, False, ["Bestseller"]),
                ("Mutton Biryani", 399, None, False, []),
                ("Veg Biryani", 249, None, True, []),
                ("Egg Biryani", 279, None, False, []),
            ],
            "Kebabs": [
                ("Seekh Kebab", 249, None, False, []),
                ("Chicken Tikka", 269, None, False, []),
                ("Paneer Tikka", 239, None, True, []),
            ],
            "Raita": [
                ("Boondi Raita", 49, None, True, []),
                ("Mix Raita", 59, None, True, []),
            ],
        },
    },
    {
        "name": "Pizza House",
        "slug": "pizza-house",
        "city": "Delhi",
        "full_address": "14 Hauz Khas Village, New Delhi",
        "latitude": 28.5494,
        "longitude": 77.2001,
        "phone": "+911123400005",
        "rating": 4.1,
        "total_reviews": 122,
        "avg_delivery_time": 40,
        "min_order_amount": 249,
        "delivery_fee": 35,
        "is_open": True,
        "is_pure_veg": False,
        "partner_phone": "+919000000005",
        "owner_name": "Vikram Arora",
        "business_type": BusinessType.RESTAURANT,
        "cuisine_types": ["Pizza", "Italian"],
        "offer": {"title": "Flat 60 off", "offer_type": OfferType.FLAT, "discount_value": 60, "min_order_amount": 299},
        "categories": {
            "Pizzas": [
                ("Margherita", 229, 199, True, ["Bestseller"]),
                ("Farmhouse", 299, None, True, []),
                ("Pepperoni Pizza", 349, None, False, []),
                ("Chicken Supreme", 369, None, False, []),
                ("Veggie Delight", 289, None, True, []),
            ],
            "Pasta": [
                ("Arrabbiata Pasta", 219, None, True, ["Spicy"]),
                ("Alfredo Pasta", 249, None, True, []),
                ("Chicken Pasta", 269, None, False, []),
            ],
            "Garlic Bread": [
                ("Classic Garlic Bread", 129, None, True, []),
                ("Cheese Garlic Bread", 159, None, True, []),
            ],
        },
    },
    {
        "name": "Green Bowl",
        "slug": "green-bowl-bangalore",
        "city": "Bangalore",
        "full_address": "9 80 Feet Road, Koramangala, Bangalore",
        "latitude": 12.9352,
        "longitude": 77.6245,
        "phone": "+918023400006",
        "rating": 4.4,
        "total_reviews": 144,
        "avg_delivery_time": 30,
        "min_order_amount": 199,
        "delivery_fee": 30,
        "is_open": True,
        "is_pure_veg": True,
        "partner_phone": "+919000000006",
        "owner_name": "Ritika Sen",
        "business_type": BusinessType.CAFE,
        "cuisine_types": ["Healthy", "Salads"],
        "offer": {"title": "10% off", "offer_type": OfferType.PERCENT, "discount_value": 10, "min_order_amount": 199},
        "categories": {
            "Bowls": [
                ("Protein Bowl", 249, None, True, ["Bestseller"]),
                ("Mexican Bowl", 239, None, True, []),
                ("Tofu Teriyaki Bowl", 259, None, True, []),
                ("Quinoa Bowl", 229, None, True, []),
            ],
            "Salads": [
                ("Caesar Salad", 199, None, True, []),
                ("Greek Salad", 189, None, True, []),
                ("Sprout Salad", 179, None, True, []),
            ],
            "Smoothies": [
                ("Berry Blast", 129, None, True, []),
                ("Mango Smoothie", 119, None, True, []),
                ("Green Detox", 139, None, True, []),
            ],
        },
    },
    {
        "name": "Wok Express",
        "slug": "wok-express",
        "city": "Bangalore",
        "full_address": "18 100 Feet Road, Indiranagar, Bangalore",
        "latitude": 12.9719,
        "longitude": 77.6412,
        "phone": "+918023400007",
        "rating": 3.9,
        "total_reviews": 98,
        "avg_delivery_time": 35,
        "min_order_amount": 179,
        "delivery_fee": 30,
        "is_open": True,
        "is_pure_veg": False,
        "partner_phone": "+919000000007",
        "owner_name": "Neeraj Verma",
        "business_type": BusinessType.RESTAURANT,
        "cuisine_types": ["Chinese", "Asian"],
        "offer": {"title": "25% off", "offer_type": OfferType.PERCENT, "discount_value": 25, "min_order_amount": 249},
        "categories": {
            "Noodles": [
                ("Hakka Noodles", 179, None, True, []),
                ("Chicken Noodles", 219, None, False, []),
                ("Schezwan Noodles", 199, None, True, ["Spicy"]),
                ("Paneer Noodles", 209, None, True, []),
            ],
            "Rice": [
                ("Veg Fried Rice", 169, None, True, []),
                ("Chicken Fried Rice", 209, None, False, []),
                ("Burnt Garlic Rice", 189, None, True, []),
            ],
            "Starters": [
                ("Spring Rolls", 149, None, True, []),
                ("Chilli Chicken", 229, None, False, ["Spicy"]),
                ("Crispy Corn", 159, None, True, []),
            ],
        },
    },
    {
        "name": "Sweet Tooth",
        "slug": "sweet-tooth",
        "city": "Bangalore",
        "full_address": "32 HSR Layout, Bangalore",
        "latitude": 12.9116,
        "longitude": 77.6474,
        "phone": "+918023400008",
        "rating": 4.7,
        "total_reviews": 188,
        "avg_delivery_time": 20,
        "min_order_amount": 99,
        "delivery_fee": 20,
        "is_open": True,
        "is_pure_veg": True,
        "partner_phone": "+919000000008",
        "owner_name": "Pooja Batra",
        "business_type": BusinessType.BAKERY,
        "cuisine_types": ["Desserts", "Bakery"],
        "offer": {"title": "Buy 1 Get 1", "offer_type": OfferType.BOGO, "discount_value": 1, "min_order_amount": 199},
        "categories": {
            "Cakes": [
                ("Chocolate Truffle Cake", 399, 349, True, ["Bestseller"]),
                ("Red Velvet Cake", 429, None, True, []),
                ("Blueberry Cheesecake", 449, None, True, []),
                ("Pineapple Cake", 329, None, True, []),
            ],
            "Ice Cream": [
                ("Belgian Chocolate Scoop", 99, None, True, []),
                ("Vanilla Bean Scoop", 89, None, True, []),
                ("Strawberry Delight Scoop", 99, None, True, []),
                ("Butterscotch Scoop", 99, None, True, []),
            ],
            "Pastries": [
                ("Black Forest Pastry", 89, None, True, []),
                ("Tiramisu Pastry", 109, None, True, []),
                ("Choco Lava Pastry", 119, None, True, []),
            ],
        },
    },
]


async def clear_existing_data(db: AsyncSession) -> None:
    for model in [
        SupportTicket,
        PartnerEarnings,
        DeliveryOtp,
        DeliveryAssignment,
        OrderResponse,
        Review,
        OrderItem,
        Order,
        MenuItem,
        MenuCategory,
        RestaurantDocument,
        RestaurantOffer,
        RestaurantTiming,
        RestaurantPayout,
        RestaurantPartner,
    ]:
        await db.execute(delete(model))

    await db.execute(delete(User).where(User.role == "RESTAURANT_PARTNER"))
    await db.execute(delete(Restaurant))
    await db.commit()


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        await clear_existing_data(db)

        for index, spec in enumerate(RESTAURANTS, start=1):
            restaurant = Restaurant(
                id=uuid.uuid4(),
                name=spec["name"],
                slug=spec["slug"],
                description=f"{spec['name']} curated for SPEC3 verification",
                cuisine_types=spec["cuisine_types"],
                city=spec["city"],
                full_address=spec["full_address"],
                latitude=spec["latitude"],
                longitude=spec["longitude"],
                phone=spec["phone"],
                rating=spec["rating"],
                total_reviews=spec["total_reviews"],
                avg_delivery_time=spec["avg_delivery_time"],
                min_order_amount=spec["min_order_amount"],
                delivery_fee=spec["delivery_fee"],
                is_open=spec["is_open"],
                is_pure_veg=spec["is_pure_veg"],
                has_offers=True,
            )
            db.add(restaurant)
            await db.flush()

            user = User(
                id=uuid.uuid4(),
                phone=spec["partner_phone"],
                name=spec["owner_name"],
                is_active=True,
                is_verified=True,
                role="RESTAURANT_PARTNER",
                restaurant_status="DOCS_APPROVED",
            )
            db.add(user)
            await db.flush()

            partner = RestaurantPartner(
                id=uuid.uuid4(),
                user_id=user.id,
                restaurant_id=restaurant.id,
                owner_name=spec["owner_name"],
                business_type=spec["business_type"],
                commission_rate=20.0,
                wallet_balance=0.0,
                total_revenue=0.0,
                total_orders=0,
                bank_account_number=f"100000000{index:02d}",
                bank_ifsc="HDFC0001234",
                bank_account_name=spec["owner_name"],
                gstin=f"27ABCDE12{index:02d}F1Z5",
                pan_number=f"ABCDE12{index:02d}F",
                fssai_number=f"1234567890{index:04d}",
                fssai_expiry=date(2027, 12, 31),
            )
            db.add(partner)
            await db.flush()

            for day in range(7):
                db.add(
                    RestaurantTiming(
                        restaurant_id=restaurant.id,
                        day_of_week=day,
                        opens_at=time(10, 0),
                        closes_at=time(23, 0),
                        is_closed=False,
                    )
                )

            for doc_type in REQUIRED_DOC_TYPES:
                db.add(
                    RestaurantDocument(
                        partner_id=partner.id,
                        doc_type=doc_type,
                        file_url=f"/uploads/restaurant/{partner.id}/{doc_type.value.lower()}.jpg",
                        file_name=f"{doc_type.value.lower()}.jpg",
                        status=DocStatus.APPROVED,
                        verified_at=datetime.now(UTC),
                    )
                )

            offer = spec["offer"]
            db.add(
                RestaurantOffer(
                    restaurant_id=restaurant.id,
                    title=offer["title"],
                    offer_type=offer["offer_type"],
                    discount_value=offer["discount_value"],
                    min_order_amount=offer["min_order_amount"],
                    is_active=True,
                )
            )

            display_order = 0
            for category_name, items in spec["categories"].items():
                category = MenuCategory(
                    id=uuid.uuid4(),
                    restaurant_id=restaurant.id,
                    name=category_name,
                    display_order=display_order,
                    is_active=True,
                )
                db.add(category)
                await db.flush()
                display_order += 1

                for item_name, price, discounted_price, is_veg, tags in items:
                    db.add(
                        MenuItem(
                            id=uuid.uuid4(),
                            restaurant_id=restaurant.id,
                            category_id=category.id,
                            name=item_name,
                            description=f"{item_name} from {spec['name']}",
                            price=price,
                            discounted_price=discounted_price,
                            is_veg=is_veg,
                            is_available=True,
                            preparation_time=20,
                            tags=tags,
                        )
                    )

        await db.commit()
        print("Seeded 8 restaurants with restaurant partner data.")


if __name__ == "__main__":
    asyncio.run(seed())
