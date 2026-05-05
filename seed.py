"""
Database seed: inserts 8 restaurants, menu categories, 40+ menu items, and 2 coupons.
Matches the actual SQLAlchemy model columns exactly.
Run: python seed.py
"""
import asyncio
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── Restaurant data ──────────────────────────────────────────────────────────

RESTAURANTS = [
    dict(name="Spice Garden", slug="spice-garden",
         description="Authentic North Indian cuisine with rich gravies.",
         cuisine_types=["Indian", "North Indian"],
         city="Bangalore", full_address="12 MG Road, Bangalore",
         phone="+919900001111", image_url=None, cover_image_url=None,
         rating=4.3, total_reviews=120, avg_delivery_time=30,
         min_order_amount=150, delivery_fee=30, is_open=True, is_pure_veg=False, has_offers=True),
    dict(name="Pizza Paradise", slug="pizza-paradise",
         description="Wood-fired Italian pizzas and pastas.",
         cuisine_types=["Italian", "Pizza"],
         city="Bangalore", full_address="5 Brigade Road, Bangalore",
         phone="+919900002222", image_url=None, cover_image_url=None,
         rating=4.1, total_reviews=85, avg_delivery_time=25,
         min_order_amount=200, delivery_fee=25, is_open=True, is_pure_veg=False, has_offers=False),
    dict(name="Wok & Roll", slug="wok-and-roll",
         description="Pan-Asian street food done right.",
         cuisine_types=["Chinese", "Thai", "Pan-Asian"],
         city="Bangalore", full_address="22 Indiranagar, Bangalore",
         phone="+919900003333", image_url=None, cover_image_url=None,
         rating=4.5, total_reviews=200, avg_delivery_time=35,
         min_order_amount=100, delivery_fee=35, is_open=True, is_pure_veg=False, has_offers=True),
    dict(name="Green Bowl", slug="green-bowl",
         description="100% vegan comfort food.",
         cuisine_types=["Vegan", "Healthy"],
         city="Mumbai", full_address="7 Bandra West, Mumbai",
         phone="+919900004444", image_url=None, cover_image_url=None,
         rating=4.6, total_reviews=150, avg_delivery_time=20,
         min_order_amount=100, delivery_fee=20, is_open=True, is_pure_veg=True, has_offers=False),
    dict(name="Burger Barn", slug="burger-barn",
         description="Gourmet smash burgers, loaded fries.",
         cuisine_types=["American", "Burgers"],
         city="Mumbai", full_address="3 Andheri East, Mumbai",
         phone="+919900005555", image_url=None, cover_image_url=None,
         rating=4.2, total_reviews=95, avg_delivery_time=22,
         min_order_amount=150, delivery_fee=30, is_open=True, is_pure_veg=False, has_offers=True),
    dict(name="Dosa Darbar", slug="dosa-darbar",
         description="Classic South Indian breakfasts and meals.",
         cuisine_types=["South Indian"],
         city="Delhi", full_address="9 Connaught Place, Delhi",
         phone="+919900006666", image_url=None, cover_image_url=None,
         rating=4.7, total_reviews=300, avg_delivery_time=15,
         min_order_amount=50, delivery_fee=15, is_open=True, is_pure_veg=True, has_offers=False),
    dict(name="Sushi Zen", slug="sushi-zen",
         description="Premium Japanese sushi and ramen.",
         cuisine_types=["Japanese", "Sushi"],
         city="Delhi", full_address="18 Khan Market, Delhi",
         phone="+919900007777", image_url=None, cover_image_url=None,
         rating=4.8, total_reviews=75, avg_delivery_time=40,
         min_order_amount=500, delivery_fee=50, is_open=True, is_pure_veg=False, has_offers=True),
    dict(name="Taco Fiesta", slug="taco-fiesta",
         description="Authentic Mexican street tacos and burritos.",
         cuisine_types=["Mexican"],
         city="Delhi", full_address="31 Hauz Khas, Delhi",
         phone="+919900008888", image_url=None, cover_image_url=None,
         rating=4.0, total_reviews=60, avg_delivery_time=28,
         min_order_amount=200, delivery_fee=25, is_open=True, is_pure_veg=False, has_offers=False),
]

# ── Menu data per restaurant slug ─────────────────────────────────────────────
# (item_name, description, price, discounted_price, category_name, is_veg, is_available, tags)

MENU_DATA = {
    "spice-garden": {
        "Starters": [
            ("Paneer Tikka", "Grilled cottage cheese with spices", 280, 249, True, True, ["Bestseller"]),
            ("Chicken Seekh Kebab", "Minced chicken on skewers", 320, None, False, True, ["Spicy"]),
        ],
        "Main Course": [
            ("Butter Chicken", "Creamy tomato curry with tender chicken", 350, 299, False, True, ["Bestseller"]),
            ("Dal Makhani", "Slow-cooked black lentils in cream", 220, None, True, True, []),
        ],
        "Breads": [
            ("Garlic Naan", "Tandoor-baked garlic flatbread", 60, None, True, True, []),
        ],
    },
    "pizza-paradise": {
        "Pizzas": [
            ("Margherita", "Classic tomato & mozzarella", 280, 249, True, True, ["Bestseller"]),
            ("Pepperoni Blast", "Double pepperoni with cheese", 380, None, False, True, ["Spicy"]),
        ],
        "Pasta": [
            ("Pasta Arrabbiata", "Spicy tomato pasta", 240, None, True, True, []),
        ],
        "Sides": [
            ("Garlic Bread", "Herb butter toasted bread", 120, 99, True, True, []),
        ],
        "Desserts": [
            ("Tiramisu", "Italian coffee dessert", 180, None, True, True, []),
        ],
    },
    "wok-and-roll": {
        "Chinese": [
            ("Kung Pao Chicken", "Spicy stir-fry with peanuts", 280, None, False, True, ["Spicy"]),
        ],
        "Thai": [
            ("Pad Thai", "Classic Thai noodles with shrimp", 250, 199, False, True, ["Bestseller"]),
            ("Green Curry", "Thai coconut milk curry", 260, None, False, True, []),
        ],
        "Starters": [
            ("Spring Rolls (Veg)", "Crispy vegetarian spring rolls", 150, None, True, True, []),
        ],
        "Rice": [
            ("Fried Rice", "Egg & vegetable wok fried rice", 180, None, False, True, []),
        ],
    },
    "green-bowl": {
        "Bowls": [
            ("Quinoa Buddha Bowl", "Roasted veggies & tahini dressing", 320, 279, True, True, ["Bestseller"]),
        ],
        "Breakfast": [
            ("Avocado Toast", "Sourdough with avocado spread", 220, None, True, True, []),
            ("Smoothie Bowl", "Acai base with granola topping", 280, 249, True, True, []),
        ],
        "Soups": [
            ("Lentil Soup", "Spiced red lentil soup", 180, None, True, True, []),
        ],
        "Desserts": [
            ("Raw Brownie", "Dates & nut chocolate brownie", 120, None, True, True, []),
        ],
    },
    "burger-barn": {
        "Burgers": [
            ("Classic Smash", "Double patty smash burger", 350, 299, False, True, ["Bestseller"]),
            ("Crispy Chicken", "Fried chicken burger", 320, None, False, True, []),
            ("Veggie Smash", "Plant-based patty burger", 300, 269, True, True, []),
        ],
        "Sides": [
            ("Loaded Fries", "Cheese sauce & jalapeños", 180, None, True, True, ["Spicy"]),
        ],
        "Beverages": [
            ("Milkshake", "Thick chocolate milkshake", 140, None, True, True, []),
        ],
    },
    "dosa-darbar": {
        "Dosas": [
            ("Masala Dosa", "Crispy dosa with potato filling", 120, 99, True, True, ["Bestseller"]),
            ("Uthappam", "Thick dosa with veggie toppings", 110, None, True, True, []),
        ],
        "Breakfast": [
            ("Idli Sambar", "Steamed rice cakes with sambar", 80, None, True, True, []),
            ("Medu Vada", "Lentil fritters with chutney", 90, None, True, True, []),
        ],
        "Beverages": [
            ("Filter Coffee", "South Indian decoction coffee", 50, None, True, True, ["Bestseller"]),
        ],
    },
    "sushi-zen": {
        "Nigiri": [
            ("Salmon Nigiri (8pc)", "Fresh salmon over seasoned rice", 680, 599, False, True, ["Bestseller"]),
        ],
        "Rolls": [
            ("Dragon Roll", "Avocado-topped inside-out roll", 780, None, False, True, []),
        ],
        "Ramen": [
            ("Miso Ramen", "Rich pork broth ramen", 550, 499, False, True, ["Bestseller"]),
        ],
        "Starters": [
            ("Edamame", "Steamed salted soybeans", 180, None, True, True, []),
        ],
        "Desserts": [
            ("Matcha Ice Cream", "Green tea soft serve", 220, None, True, True, []),
        ],
    },
    "taco-fiesta": {
        "Tacos": [
            ("Carne Asada Taco", "Grilled beef taco (3pc)", 320, 279, False, True, ["Bestseller"]),
        ],
        "Burritos": [
            ("Veggie Burrito", "Black bean & rice burrito", 280, None, True, True, []),
        ],
        "Quesadillas": [
            ("Chicken Quesadilla", "Grilled cheese & chicken", 300, None, False, True, []),
        ],
        "Sides": [
            ("Guacamole & Chips", "House-made guacamole", 180, None, True, True, []),
        ],
        "Desserts": [
            ("Churros", "Fried dough with chocolate dip", 150, None, True, True, []),
        ],
    },
}

# ── Coupons ───────────────────────────────────────────────────────────────────

COUPONS = [
    dict(code="WELCOME50", description="50% off up to ₹100 on first order",
         discount_type="PERCENT", discount_value=50, min_order_amount=100,
         max_discount=100, is_active=True),
    dict(code="FLAT100", description="Flat ₹100 off on orders above ₹400",
         discount_type="FLAT", discount_value=100, min_order_amount=400,
         max_discount=None, is_active=True),
]


async def seed() -> None:
    async with SessionLocal() as db:
        # Clear existing data in correct FK order
        for table in ["reviews", "order_items", "orders", "cart_items",
                      "menu_items", "menu_categories", "coupons", "restaurants"]:
            await db.execute(text(f"DELETE FROM {table}"))

        restaurant_ids = {}

        # Insert restaurants
        for r in RESTAURANTS:
            rid = uuid.uuid4()
            restaurant_ids[r["slug"]] = rid
            await db.execute(text("""
                INSERT INTO restaurants
                  (id, name, slug, description, cuisine_types, city, full_address,
                   phone, image_url, cover_image_url, rating, total_reviews,
                   avg_delivery_time, min_order_amount, delivery_fee,
                   is_open, is_pure_veg, has_offers)
                VALUES
                  (:id, :name, :slug, :description, CAST(:cuisine_types AS varchar[]), :city, :full_address,
                   :phone, :image_url, :cover_image_url, :rating, :total_reviews,
                   :avg_delivery_time, :min_order_amount, :delivery_fee,
                   :is_open, :is_pure_veg, :has_offers)
            """), {**r, "id": rid, "cuisine_types": r["cuisine_types"]})

        # Insert menu categories and items
        total_items = 0
        total_categories = 0
        for slug, categories in MENU_DATA.items():
            rid = restaurant_ids[slug]
            for display_order, (cat_name, items) in enumerate(categories.items()):
                cat_id = uuid.uuid4()
                await db.execute(text("""
                    INSERT INTO menu_categories (id, restaurant_id, name, display_order, is_active)
                    VALUES (:id, :restaurant_id, :name, :display_order, TRUE)
                """), {"id": cat_id, "restaurant_id": rid,
                       "name": cat_name, "display_order": display_order})
                total_categories += 1

                for item_name, desc, price, disc_price, is_veg, is_avail, tags in items:
                    await db.execute(text("""
                        INSERT INTO menu_items
                          (id, restaurant_id, category_id, name, description,
                           price, discounted_price, is_veg, is_available, tags)
                        VALUES
                          (:id, :restaurant_id, :category_id, :name, :description,
                           :price, :discounted_price, :is_veg, :is_available, CAST(:tags AS varchar[]))
                    """), {
                        "id": uuid.uuid4(), "restaurant_id": rid, "category_id": cat_id,
                        "name": item_name, "description": desc,
                        "price": price, "discounted_price": disc_price,
                        "is_veg": is_veg, "is_available": is_avail, "tags": tags,
                    })
                    total_items += 1

        # Insert coupons
        for c in COUPONS:
            await db.execute(text("""
                INSERT INTO coupons
                  (id, code, description, discount_type, discount_value,
                   min_order_amount, max_discount, is_active)
                VALUES
                  (:id, :code, :description, CAST(:discount_type AS discounttype), :discount_value,
                   :min_order_amount, :max_discount, :is_active)
            """), {**c, "id": uuid.uuid4()})

        await db.commit()
        print(f"[OK] Seeded {len(RESTAURANTS)} restaurants, "
              f"{total_categories} categories, "
              f"{total_items} menu items, "
              f"{len(COUPONS)} coupons.")


if __name__ == "__main__":
    asyncio.run(seed())
