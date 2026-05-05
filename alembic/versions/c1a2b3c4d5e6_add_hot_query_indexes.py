"""add hot query indexes

Revision ID: c1a2b3c4d5e6
Revises: b0f4c2d8a901
Create Date: 2026-05-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c1a2b3c4d5e6"
down_revision: Union[str, None] = "b0f4c2d8a901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_city ON restaurants(city)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_rating ON restaurants(rating DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_restaurants_is_open ON restaurants(is_open) WHERE is_open=TRUE")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cart_user_id ON cart_items(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cart_restaurant ON cart_items(user_id, restaurant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_restaurant_status ON orders(restaurant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_assignments_partner_status ON delivery_assignments(partner_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_partner_loc_partner_time ON partner_locations(partner_id, recorded_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_menu_items_restaurant ON menu_items(restaurant_id, is_available)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reviews_restaurant ON reviews(restaurant_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_reviews_restaurant")
    op.execute("DROP INDEX IF EXISTS idx_menu_items_restaurant")
    op.execute("DROP INDEX IF EXISTS idx_partner_loc_partner_time")
    op.execute("DROP INDEX IF EXISTS idx_assignments_partner_status")
    op.execute("DROP INDEX IF EXISTS idx_orders_restaurant_status")
    op.execute("DROP INDEX IF EXISTS idx_orders_user_created")
    op.execute("DROP INDEX IF EXISTS idx_cart_restaurant")
    op.execute("DROP INDEX IF EXISTS idx_cart_user_id")
    op.execute("DROP INDEX IF EXISTS idx_restaurants_is_open")
    op.execute("DROP INDEX IF EXISTS idx_restaurants_rating")
    op.execute("DROP INDEX IF EXISTS idx_restaurants_city")
