import uuid
import enum
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, String, func, text, Enum as SAEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class DocType(str, enum.Enum):
    FSSAI_LICENSE = "FSSAI_LICENSE"
    GST_CERTIFICATE = "GST_CERTIFICATE"
    PAN_CARD = "PAN_CARD"
    BANK_CANCELLED_CHEQUE = "BANK_CANCELLED_CHEQUE"
    OWNER_AADHAAR_FRONT = "OWNER_AADHAAR_FRONT"
    OWNER_AADHAAR_BACK = "OWNER_AADHAAR_BACK"
    SHOP_ACT_LICENSE = "SHOP_ACT_LICENSE"
    PARTNERSHIP_DEED = "PARTNERSHIP_DEED"
    MENU_PHOTO = "MENU_PHOTO"
    RESTAURANT_PHOTO_FRONT = "RESTAURANT_PHOTO_FRONT"
    RESTAURANT_PHOTO_INTERIOR = "RESTAURANT_PHOTO_INTERIOR"

class DocStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class RestaurantDocument(Base):
    __tablename__ = "restaurant_documents"
    __table_args__ = (
        UniqueConstraint("partner_id", "doc_type", name="uq_restaurant_doc"),
        Index("ix_restaurant_documents_partner_id", "partner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("restaurant_partners.id", ondelete="CASCADE"), nullable=False)
    doc_type: Mapped[DocType] = mapped_column(SAEnum(DocType, name="restaurant_doc_type_enum"), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[DocStatus] = mapped_column(SAEnum(DocStatus, name="restaurant_doc_status_enum"), server_default=text("'PENDING'"), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    partner = relationship("RestaurantPartner")
