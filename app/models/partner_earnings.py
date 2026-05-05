"""
PartnerEarnings ORM model — exactly per SPEC2.md Section 3.

Per-delivery earnings breakdown:
  base_pay       = ₹25 flat
  distance_pay   = ₹8/km beyond 3 km
  surge_pay      = peak-hour / rain / weekend bonus
  incentive_pay  = daily/weekly slab bonus
  tip_amount     = customer tip
  total_earned   = sum of above

INDEX on (partner_id, earned_at DESC).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PartnerEarnings(Base):
    __tablename__ = "partner_earnings"
    __table_args__ = (
        Index("ix_partner_earnings_partner_earned", "partner_id", "earned_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_partners.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_assignments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )

    base_pay: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    distance_pay: Mapped[float] = mapped_column(
        Numeric(8, 2), server_default=text("0"), nullable=False,
    )
    surge_pay: Mapped[float] = mapped_column(
        Numeric(8, 2), server_default=text("0"), nullable=False,
    )
    incentive_pay: Mapped[float] = mapped_column(
        Numeric(8, 2), server_default=text("0"), nullable=False,
    )
    tip_amount: Mapped[float] = mapped_column(
        Numeric(8, 2), server_default=text("0"), nullable=False,
    )
    total_earned: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # Relationships
    partner: Mapped["DeliveryPartner"] = relationship(
        "DeliveryPartner", back_populates="earnings", lazy="noload",
    )
    assignment: Mapped["DeliveryAssignment"] = relationship(
        "DeliveryAssignment", back_populates="earnings", lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<PartnerEarnings partner_id={self.partner_id} total={self.total_earned}>"
