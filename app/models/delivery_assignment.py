"""
DeliveryAssignment ORM model — exactly per SPEC2.md Section 3.

Links an order to a delivery partner.
Includes all status snapshots: restaurant lat/lng, customer lat/lng,
customer_address, customer_name, customer_phone (masked).

STATUS enum with 9 values as per spec.
UNIQUE on order_id (one active assignment per order).
INDEX on (partner_id, status), INDEX on (order_id).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AssignmentStatus(str, enum.Enum):
    ASSIGNED = "ASSIGNED"           # partner notified
    ACCEPTED = "ACCEPTED"           # partner accepted
    REJECTED = "REJECTED"           # partner rejected
    TIMED_OUT = "TIMED_OUT"         # no response in 45s
    REACHED_RESTAURANT = "REACHED_RESTAURANT"   # partner at pickup
    PICKED_UP = "PICKED_UP"         # food in hand
    REACHED_CUSTOMER = "REACHED_CUSTOMER"       # at delivery location
    DELIVERED = "DELIVERED"         # completed
    FAILED = "FAILED"               # could not deliver


class DeliveryAssignment(Base):
    __tablename__ = "delivery_assignments"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_assignment_order"),
        Index("ix_da_partner_status", "partner_id", "status"),
        Index("ix_da_order_id", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_partners.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, name="assignmentstatus"),
        server_default=text("'ASSIGNED'"),
        nullable=False,
    )

    # Timestamps
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Route info
    distance_km: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    # Snapshots at assignment time (never change)
    restaurant_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    restaurant_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    customer_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    customer_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(15), nullable=True)  # masked

    # Relationships
    order: Mapped["Order"] = relationship("Order", lazy="selectin")
    partner: Mapped["DeliveryPartner"] = relationship(
        "DeliveryPartner", back_populates="assignments", lazy="selectin",
    )
    delivery_otp: Mapped["DeliveryOtp | None"] = relationship(
        "DeliveryOtp", back_populates="assignment", uselist=False, lazy="noload",
    )
    earnings: Mapped["PartnerEarnings | None"] = relationship(
        "PartnerEarnings", back_populates="assignment", uselist=False, lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<DeliveryAssignment id={self.id} status={self.status}>"
