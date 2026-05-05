"""
Payout ORM model — exactly per SPEC2.md Section 3.

Weekly payout records (Zomato pays every Monday).
status ENUM: PENDING | PROCESSING | PAID | FAILED
INDEX on (partner_id, status).
"""
import enum
import uuid
from datetime import datetime, date

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PayoutStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    FAILED = "FAILED"


class Payout(Base):
    __tablename__ = "payouts"
    __table_args__ = (
        Index("ix_payouts_partner_status", "partner_id", "status"),
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
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    payout_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    payout_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PayoutStatus] = mapped_column(
        Enum(PayoutStatus, name="payoutstatus"),
        server_default=text("'PENDING'"),
        nullable=False,
    )
    bank_account: Mapped[str | None] = mapped_column(String(20), nullable=True)  # last 4 digits
    utr_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    partner: Mapped["DeliveryPartner"] = relationship(
        "DeliveryPartner", back_populates="payouts", lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Payout partner_id={self.partner_id} amount={self.amount} status={self.status}>"
