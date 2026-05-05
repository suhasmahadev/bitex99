"""
PartnerIncentive ORM model — exactly per SPEC2.md Section 3.

Records each incentive bonus earned by a partner.
payout_id nullable — set when this incentive is included in a payout.
INDEX on (partner_id, earned_at DESC).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PartnerIncentive(Base):
    __tablename__ = "partner_incentives"
    __table_args__ = (
        Index("ix_partner_incentives_partner_earned", "partner_id", "earned_at"),
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
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incentive_rules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    bonus_amount: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    payout_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payouts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    partner: Mapped["DeliveryPartner"] = relationship(
        "DeliveryPartner", back_populates="incentives", lazy="noload",
    )
    rule: Mapped["IncentiveRule"] = relationship(
        "IncentiveRule", back_populates="partner_incentives", lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<PartnerIncentive partner_id={self.partner_id} "
            f"bonus={self.bonus_amount} earned_at={self.earned_at}>"
        )
