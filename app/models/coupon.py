"""
Coupon ORM model — exactly per SPEC.md Section 4.
discount_type: ENUM('FLAT','PERCENT')
max_uses/used_count (not usage_limit/times_used)
No restaurant_id FK — global coupons only per spec.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, func, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DiscountType(str, enum.Enum):
    FLAT = "FLAT"
    PERCENT = "PERCENT"


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType, name="discounttype"), nullable=False,
    )
    discount_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    min_order_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), server_default=text("0"), nullable=False,
    )
    max_discount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), nullable=False,
    )

    # Restaurant-specific coupon support (optional FK, NULL = global)
    restaurant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    restaurant: Mapped["Restaurant | None"] = relationship(
        "Restaurant", back_populates="coupons",
        primaryjoin="Coupon.restaurant_id == Restaurant.id",
        foreign_keys="[Coupon.restaurant_id]",
    )

    def __repr__(self) -> str:
        return f"<Coupon code={self.code} type={self.discount_type}>"
