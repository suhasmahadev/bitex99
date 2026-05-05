import uuid
import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, func, text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class OfferType(str, enum.Enum):
    FLAT = "FLAT"
    PERCENT = "PERCENT"
    FREE_DELIVERY = "FREE_DELIVERY"
    BOGO = "BOGO"

class RestaurantOffer(Base):
    __tablename__ = "restaurant_offers"
    __table_args__ = (
        Index("ix_restaurant_offers_restaurant_is_active", "restaurant_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    offer_type: Mapped[OfferType] = mapped_column(SAEnum(OfferType, name="restaurant_offer_type_enum"), nullable=False)
    discount_value: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    max_discount: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    min_order_amount: Mapped[float] = mapped_column(Numeric(10, 2), server_default=text("0.00"), nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    restaurant = relationship("Restaurant")
