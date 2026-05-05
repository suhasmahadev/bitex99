"""
IncentiveRule ORM model — exactly per SPEC2.md Section 3.

Configurable bonus rules — seeded in seed_partner.py.
type ENUM: DAILY_ORDERS | WEEKLY_ORDERS | PEAK_HOUR | RAIN_BONUS |
           CONSECUTIVE_DAYS | ACCEPTANCE_RATE
city NULL = applies to all cities.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IncentiveType(str, enum.Enum):
    DAILY_ORDERS = "DAILY_ORDERS"
    WEEKLY_ORDERS = "WEEKLY_ORDERS"
    PEAK_HOUR = "PEAK_HOUR"
    RAIN_BONUS = "RAIN_BONUS"
    CONSECUTIVE_DAYS = "CONSECUTIVE_DAYS"
    ACCEPTANCE_RATE = "ACCEPTANCE_RATE"


class IncentiveRule(Base):
    __tablename__ = "incentive_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True,
        server_default=text("gen_random_uuid()"), default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[IncentiveType] = mapped_column(
        Enum(IncentiveType, name="incentivetype"), nullable=False,
    )
    threshold_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bonus_amount: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)  # NULL = all cities
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("TRUE"), nullable=False,
    )

    # Relationships
    partner_incentives: Mapped[list["PartnerIncentive"]] = relationship(
        "PartnerIncentive", back_populates="rule", lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<IncentiveRule name={self.name} type={self.type} bonus={self.bonus_amount}>"
