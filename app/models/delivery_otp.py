"""
DeliveryOtp ORM model — exactly per SPEC2.md Section 3.

4-digit OTP used to confirm delivery to customer.
UNIQUE on assignment_id (one OTP per assignment).
expires_at = created_at + 30 minutes (set in service layer).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeliveryOtp(Base):
    __tablename__ = "delivery_otps"
    __table_args__ = (
        UniqueConstraint("assignment_id", name="uq_delivery_otp_assignment"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    otp: Mapped[str] = mapped_column(String(4), nullable=False)
    is_used: Mapped[bool] = mapped_column(
        Boolean, server_default=text("FALSE"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    # Service sets this to created_at + 30 minutes
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    assignment: Mapped["DeliveryAssignment"] = relationship(
        "DeliveryAssignment", back_populates="delivery_otp",
    )

    def __repr__(self) -> str:
        return f"<DeliveryOtp assignment_id={self.assignment_id} is_used={self.is_used}>"
