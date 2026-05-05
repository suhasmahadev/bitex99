"""
Review ORM model — exactly per SPEC.md Section 4.
CRITICAL:
  - food_rating INTEGER (not Float rating)
  - delivery_rating INTEGER with CHECK 1-5
  - image_urls VARCHAR[]
  - UNIQUE on order_id (one review per order)
  - INDEX on restaurant_id
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String

from app.database import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_review_order"),
        CheckConstraint("food_rating BETWEEN 1 AND 5", name="ck_food_rating"),
        CheckConstraint("delivery_rating BETWEEN 1 AND 5", name="ck_delivery_rating"),
        Index("ix_reviews_restaurant_id", "restaurant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
    )
    food_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_urls: Mapped[list] = mapped_column(
        ARRAY(String(500)), nullable=False, server_default=text("'{}'::varchar[]"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="reviews")
    order: Mapped["Order"] = relationship("Order", back_populates="review")
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Review id={self.id} food={self.food_rating} delivery={self.delivery_rating}>"
