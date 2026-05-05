"""
Order, OrderItem ORM models + all enums — exactly per SPEC.md Section 4.
CRITICAL:
  - OrderStatus includes READY_FOR_PICKUP and FAILED
  - PaymentStatus enum: PENDING, SUCCESS, FAILED, REFUNDED
  - delivery_address_snapshot JSONB NOT NULL (frozen at order time)
  - Column names: items_total, discount_amount, total_amount
  - cancellation_reason TEXT
  - estimated_delivery_at TIMESTAMPTZ (not minutes)
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.coupon import Coupon


class OrderStatus(str, enum.Enum):
    PLACED = "PLACED"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class PaymentMethod(str, enum.Enum):
    COD = "COD"
    UPI = "UPI"
    CARD = "CARD"
    WALLET = "WALLET"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


# SPEC Section 7 — enforced in order_service.py
VALID_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.PLACED:           [OrderStatus.CONFIRMED, OrderStatus.CANCELLED, OrderStatus.FAILED],
    OrderStatus.CONFIRMED:        [OrderStatus.PREPARING, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED],
    OrderStatus.PREPARING:        [OrderStatus.READY_FOR_PICKUP],
    OrderStatus.READY_FOR_PICKUP: [OrderStatus.OUT_FOR_DELIVERY],
    OrderStatus.OUT_FOR_DELIVERY: [OrderStatus.DELIVERED, OrderStatus.FAILED],
    OrderStatus.DELIVERED:        [],  # terminal
    OrderStatus.CANCELLED:        [],  # terminal
    OrderStatus.FAILED:           [],  # terminal
}

# Statuses the USER can cancel from (SPEC Section 7)
USER_CANCELLABLE_STATUSES = {OrderStatus.PLACED, OrderStatus.CONFIRMED}


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_id", "user_id"),
        Index("ix_orders_status", "status"),
        Index("ix_orders_created_at_desc", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    delivery_address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("addresses.id", ondelete="SET NULL"),
        nullable=True,
    )
    # CRITICAL: frozen snapshot of address at order time — never changes
    delivery_address_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    items_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    delivery_fee: Mapped[float] = mapped_column(
        Numeric(10, 2), server_default=text("0"), nullable=False,
    )
    discount_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), server_default=text("0"), nullable=False,
    )
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    coupon_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="paymentmethod"), nullable=False,
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="paymentstatus"),
        server_default=text("'PENDING'"),
        nullable=False,
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="orderstatus"),
        server_default=text("'PLACED'"),
        nullable=False,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preparation_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    restaurant_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders")
    restaurant: Mapped["Restaurant"] = relationship("Restaurant", lazy="selectin")
    delivery_address: Mapped["Address | None"] = relationship("Address", lazy="selectin")
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", lazy="selectin", cascade="all, delete-orphan",
    )
    review: Mapped["Review | None"] = relationship(
        "Review", back_populates="order", uselist=False, lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Order id={self.id} status={self.status}>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    menu_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Snapshots at order time — never change even if menu_item is deleted
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Numeric(10, 0), nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    menu_item: Mapped["MenuItem | None"] = relationship("MenuItem", lazy="selectin")

    def __repr__(self) -> str:
        return f"<OrderItem name={self.name} qty={self.quantity}>"
