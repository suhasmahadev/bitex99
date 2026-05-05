"""
CartItem ORM model — exactly per SPEC.md Section 4.
CRITICAL:
  - restaurant_id FK enforces single-restaurant cart constraint
  - UNIQUE(user_id, menu_item_id) — one row per user+item
  - CHECK(quantity >= 1)
  - Composite index on (user_id, restaurant_id)
  - added_at (not created_at)
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("user_id", "menu_item_id", name="uq_cart_user_item"),
        CheckConstraint("quantity >= 1", name="ck_cart_quantity_positive"),
        Index("ix_cart_items_user_id", "user_id"),
        Index("ix_cart_items_user_restaurant", "user_id", "restaurant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # CRITICAL: denormalized restaurant_id for single-restaurant constraint enforcement
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
    )
    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="cart_items")
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", lazy="selectin")
    menu_item: Mapped["MenuItem"] = relationship("MenuItem", lazy="selectin")

    def __repr__(self) -> str:
        return f"<CartItem user={self.user_id} item={self.menu_item_id} qty={self.quantity}>"
