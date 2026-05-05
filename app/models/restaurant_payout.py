import uuid
import enum
from datetime import datetime, date
from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, func, text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class PayoutStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    FAILED = "FAILED"

class RestaurantPayout(Base):
    __tablename__ = "restaurant_payouts"
    __table_args__ = (
        Index("ix_restaurant_payouts_partner_status", "partner_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("restaurant_partners.id", ondelete="CASCADE"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    gross_revenue: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    commission_deducted: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    net_payout: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PayoutStatus] = mapped_column(SAEnum(PayoutStatus, name="restaurant_payout_status_enum"), server_default=text("'PENDING'"), nullable=False)
    bank_account: Mapped[str | None] = mapped_column(String(20), nullable=True)
    utr_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    initiated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    partner = relationship("RestaurantPartner")
