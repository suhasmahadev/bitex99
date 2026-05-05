"""
DeliveryPartner ORM model — exactly per SPEC2.md Section 3.

Columns:
  fe_id VARCHAR(20) UNIQUE          — Fleet Executive ID e.g. "ZFE00123"
  is_online BOOLEAN DEFAULT FALSE   — duty toggle
  wallet_balance NUMERIC(12,2)      — earned not yet paid out
  acceptance_rate NUMERIC(5,2)      — %
  completion_rate NUMERIC(5,2)      — %
  referred_by → delivery_partners.id (self-referential, nullable)
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Numeric, String, Integer, func, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VehicleType(str, enum.Enum):
    BIKE = "BIKE"
    SCOOTER = "SCOOTER"
    CYCLE = "CYCLE"
    EV_BIKE = "EV_BIKE"


class DeliveryPartner(Base):
    __tablename__ = "delivery_partners"
    __table_args__ = (
        Index("ix_dp_city", "city"),
        Index("ix_dp_is_online_city", "is_online", "city"),
        Index("ix_dp_location", "current_latitude", "current_longitude"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    fe_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    vehicle_type: Mapped[VehicleType | None] = mapped_column(
        String(20), nullable=True,
    )
    vehicle_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vehicle_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Duty toggle
    is_online: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False,
    )

    # Live location
    current_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    current_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    last_location_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Performance metrics
    rating: Mapped[float] = mapped_column(
        Numeric(3, 2), server_default=text("5.0"), nullable=False,
    )
    total_ratings: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False,
    )
    acceptance_rate: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default=text("100.0"), nullable=False,
    )
    completion_rate: Mapped[float] = mapped_column(
        Numeric(5, 2), server_default=text("100.0"), nullable=False,
    )
    total_deliveries: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False,
    )
    total_earnings: Mapped[float] = mapped_column(
        Numeric(12, 2), server_default=text("0.00"), nullable=False,
    )
    wallet_balance: Mapped[float] = mapped_column(
        Numeric(12, 2), server_default=text("0.00"), nullable=False,
    )

    # Referral
    referral_code: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    referred_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_partners.id", ondelete="SET NULL"),
        nullable=True,
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="selectin")
    kyc_documents: Mapped[list["KycDocument"]] = relationship(
        "KycDocument", back_populates="partner", lazy="noload", cascade="all, delete-orphan",
    )
    shifts: Mapped[list["PartnerShift"]] = relationship(
        "PartnerShift", back_populates="partner", lazy="noload",
    )
    assignments: Mapped[list["DeliveryAssignment"]] = relationship(
        "DeliveryAssignment", back_populates="partner", lazy="noload",
    )
    earnings: Mapped[list["PartnerEarnings"]] = relationship(
        "PartnerEarnings", back_populates="partner", lazy="noload",
    )
    payouts: Mapped[list["Payout"]] = relationship(
        "Payout", back_populates="partner", lazy="noload",
    )
    incentives: Mapped[list["PartnerIncentive"]] = relationship(
        "PartnerIncentive", back_populates="partner", lazy="noload",
    )
    support_tickets: Mapped[list["SupportTicket"]] = relationship(
        "SupportTicket", back_populates="partner", lazy="noload",
    )
    # Self-referential referrals
    referrals: Mapped[list["DeliveryPartner"]] = relationship(
        "DeliveryPartner",
        foreign_keys="[DeliveryPartner.referred_by]",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<DeliveryPartner fe_id={self.fe_id} city={self.city}>"
