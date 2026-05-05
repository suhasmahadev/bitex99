"""
MenuCategory and MenuItem ORM models — exactly per SPEC.md Section 4.
CRITICAL: discounted_price is nullable — NULL means no discount.
          category_id FK links MenuItem to MenuCategory.
          tags is VARCHAR[] array.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MenuCategory(Base):
    __tablename__ = "menu_categories"
    __table_args__ = (
        Index("ix_menu_categories_restaurant_id", "restaurant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), nullable=False,
    )

    restaurant: Mapped["Restaurant"] = relationship(
        "Restaurant", back_populates="menu_categories",
    )
    menu_items: Mapped[list["MenuItem"]] = relationship(
        "MenuItem", back_populates="category", lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MenuCategory id={self.id} name={self.name}>"


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        Index("ix_menu_items_restaurant_id", "restaurant_id"),
        Index("ix_menu_items_category_id", "category_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # NULL means no discount; effective_price = discounted_price ?? price
    discounted_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_veg: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), nullable=False,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), nullable=False,
    )
    preparation_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[list] = mapped_column(
        ARRAY(String(100)), nullable=False, server_default=text("'{}'::varchar[]"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    restaurant: Mapped["Restaurant"] = relationship("Restaurant", back_populates="menu_items")
    category: Mapped["MenuCategory"] = relationship("MenuCategory", back_populates="menu_items")

    @property
    def effective_price(self) -> float:
        """Returns discounted_price if set, otherwise price."""
        return float(self.discounted_price) if self.discounted_price is not None else float(self.price)

    def __repr__(self) -> str:
        return f"<MenuItem id={self.id} name={self.name}>"
