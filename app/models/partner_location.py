"""
PartnerLocation ORM model — exactly per SPEC2.md Section 3.

Live GPS position history log.
Retain last 24 hours only (cleanup via background task per Section 18).
INDEX on (partner_id, recorded_at DESC).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PartnerLocation(Base):
    __tablename__ = "partner_locations"
    __table_args__ = (
        Index("ix_partner_locations_partner_recorded", "partner_id", "recorded_at"),
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
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    speed_kmph: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    heading_degrees: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-360
    accuracy_meters: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # Relationships
    partner: Mapped["DeliveryPartner"] = relationship("DeliveryPartner", lazy="noload")

    def __repr__(self) -> str:
        return f"<PartnerLocation partner_id={self.partner_id} lat={self.latitude} lng={self.longitude}>"
