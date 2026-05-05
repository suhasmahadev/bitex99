"""
SupportTicket ORM model — exactly per SPEC2.md Section 3.

In-app support ticket system for delivery partners.
category ENUM: EARNINGS | ORDER_ISSUE | APP_BUG | PAYMENT |
               ACCOUNT | SAFETY | OTHER
status ENUM: OPEN | IN_PROGRESS | RESOLVED | CLOSED
assignment_id nullable — set if ticket relates to a specific delivery.
INDEX on (partner_id, status).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TicketCategory(str, enum.Enum):
    EARNINGS = "EARNINGS"
    ORDER_ISSUE = "ORDER_ISSUE"
    APP_BUG = "APP_BUG"
    PAYMENT = "PAYMENT"
    ACCOUNT = "ACCOUNT"
    SAFETY = "SAFETY"
    OTHER = "OTHER"


class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        Index("ix_support_tickets_partner_status", "partner_id", "status"),
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
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_assignments.id", ondelete="SET NULL"),
        nullable=True,
    )
    category: Mapped[TicketCategory] = mapped_column(
        Enum(TicketCategory, name="ticketcategory"), nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticketstatus"),
        server_default=text("'OPEN'"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    partner: Mapped["DeliveryPartner"] = relationship(
        "DeliveryPartner", back_populates="support_tickets", lazy="noload",
    )

    def __repr__(self) -> str:
        return (
            f"<SupportTicket partner_id={self.partner_id} "
            f"category={self.category} status={self.status}>"
        )
