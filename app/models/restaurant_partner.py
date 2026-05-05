import uuid
import enum
from datetime import datetime, date
from sqlalchemy import Boolean, DateTime, Date, ForeignKey, Index, Integer, Numeric, String, func, text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class BusinessType(str, enum.Enum):
    RESTAURANT = "RESTAURANT"
    CLOUD_KITCHEN = "CLOUD_KITCHEN"
    BAKERY = "BAKERY"
    CAFE = "CAFE"
    FOOD_TRUCK = "FOOD_TRUCK"

class RestaurantPartner(Base):
    __tablename__ = "restaurant_partners"
    __table_args__ = (
        Index("ix_restaurant_partners_restaurant_id", "restaurant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("restaurants.id"), unique=True, nullable=False)
    owner_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_type: Mapped[BusinessType] = mapped_column(SAEnum(BusinessType, name="business_type_enum"), nullable=False)
    commission_rate: Mapped[float] = mapped_column(Numeric(5, 2), server_default=text("20.00"), nullable=False)
    wallet_balance: Mapped[float] = mapped_column(Numeric(12, 2), server_default=text("0.00"), nullable=False)
    total_revenue: Mapped[float] = mapped_column(Numeric(14, 2), server_default=text("0.00"), nullable=False)
    total_orders: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    bank_account_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String(15), nullable=True)
    bank_account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pan_number: Mapped[str | None] = mapped_column(String(15), nullable=True)
    fssai_number: Mapped[str] = mapped_column(String(20), nullable=False)
    fssai_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")
    restaurant = relationship("Restaurant")
