"""
PartnerShift ORM model — exactly per SPEC2.md Section 3.

Tracks login/logout sessions.
duration_minutes computed on shift end.
INDEX on (partner_id, started_at DESC).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PartnerShift(Base):
    __tablename__ = "partner_shifts"
    __table_args__ = (
        Index("ix_partner_shifts_partner_started", "partner_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Computed on shift end: difference in minutes
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deliveries_in_shift: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False,
    )
    earnings_in_shift: Mapped[float] = mapped_column(
        Numeric(10, 2), server_default=text("0.00"), nullable=False,
    )
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    partner: Mapped["DeliveryPartner"] = relationship("DeliveryPartner", back_populates="shifts")

    def __repr__(self) -> str:
        return f"<PartnerShift partner_id={self.partner_id} started_at={self.started_at}>"
