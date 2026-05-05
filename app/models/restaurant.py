"""
Restaurant ORM model — exactly per SPEC.md Section 4.
Includes: phone, cover_image_url, min_order_amount, delivery_fee,
          is_pure_veg, has_offers, rating NUMERIC(3,2).
GIN index on cuisine_types, indexes on city and rating.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Index, Integer, Numeric, String, Text, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Restaurant(Base):
    __tablename__ = "restaurants"
    __table_args__ = (
        Index("ix_restaurants_city", "city"),
        Index("ix_restaurants_rating_desc", "rating"),
        # GIN index on cuisine_types for array contains queries
        Index("ix_restaurants_cuisine_types_gin", "cuisine_types", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cuisine_types: Mapped[list] = mapped_column(
        ARRAY(String(100)), nullable=False, server_default=text("'{}'::varchar[]"),
    )
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    full_address: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rating: Mapped[float] = mapped_column(
        Numeric(3, 2), server_default=text("0.0"), nullable=False,
    )
    total_reviews: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False,
    )
    avg_delivery_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_order_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), server_default=text("0"), nullable=False,
    )
    delivery_fee: Mapped[float] = mapped_column(
        Numeric(10, 2), server_default=text("0"), nullable=False,
    )
    is_open: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), nullable=False,
    )
    is_pure_veg: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False,
    )
    has_offers: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # Relationships
    menu_categories: Mapped[list["MenuCategory"]] = relationship(
        "MenuCategory", back_populates="restaurant", lazy="selectin",
        cascade="all, delete-orphan",
    )
    menu_items: Mapped[list["MenuItem"]] = relationship(
        "MenuItem", back_populates="restaurant", lazy="noload",
        cascade="all, delete-orphan",
    )
    coupons: Mapped[list["Coupon"]] = relationship(
        "Coupon", back_populates="restaurant", lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Restaurant id={self.id} name={self.name}>"
