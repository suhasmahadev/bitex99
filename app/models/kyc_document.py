"""
KycDocument ORM model — exactly per SPEC2.md Section 3.

doc_type ENUM with all 10 values including POLICE_VERIFICATION (optional doc).
UNIQUE on (partner_id, doc_type) — one record per document type per partner.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocType(str, enum.Enum):
    AADHAAR_FRONT = "AADHAAR_FRONT"
    AADHAAR_BACK = "AADHAAR_BACK"
    PAN_CARD = "PAN_CARD"
    DRIVING_LICENSE_FRONT = "DRIVING_LICENSE_FRONT"
    DRIVING_LICENSE_BACK = "DRIVING_LICENSE_BACK"
    VEHICLE_RC = "VEHICLE_RC"
    VEHICLE_INSURANCE = "VEHICLE_INSURANCE"
    BANK_PASSBOOK = "BANK_PASSBOOK"
    PROFILE_PHOTO = "PROFILE_PHOTO"
    POLICE_VERIFICATION = "POLICE_VERIFICATION"


class DocStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# Required documents (POLICE_VERIFICATION is optional)
REQUIRED_DOC_TYPES = {
    DocType.AADHAAR_FRONT,
    DocType.AADHAAR_BACK,
    DocType.PAN_CARD,
    DocType.DRIVING_LICENSE_FRONT,
    DocType.DRIVING_LICENSE_BACK,
    DocType.VEHICLE_RC,
    DocType.VEHICLE_INSURANCE,
    DocType.BANK_PASSBOOK,
    DocType.PROFILE_PHOTO,
}


class KycDocument(Base):
    __tablename__ = "kyc_documents"
    __table_args__ = (
        UniqueConstraint("partner_id", "doc_type", name="uq_kyc_partner_doc_type"),
        Index("ix_kyc_partner_id", "partner_id"),
        Index("ix_kyc_status", "status"),
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
    doc_type: Mapped[DocType] = mapped_column(
        Enum(DocType, name="doctype"), nullable=False,
    )
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[DocStatus] = mapped_column(
        Enum(DocStatus, name="docstatus"),
        server_default=text("'PENDING'"),
        nullable=False,
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # Relationships
    partner: Mapped["DeliveryPartner"] = relationship(
        "DeliveryPartner", back_populates="kyc_documents",
    )

    def __repr__(self) -> str:
        return f"<KycDocument partner_id={self.partner_id} doc_type={self.doc_type} status={self.status}>"
