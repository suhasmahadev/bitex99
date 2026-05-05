import uuid
from datetime import time
from sqlalchemy import Boolean, ForeignKey, Index, Integer, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class RestaurantTiming(Base):
    __tablename__ = "restaurant_timings"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "day_of_week", name="uq_restaurant_timing"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    opens_at: Mapped[time] = mapped_column(Time, nullable=False)
    closes_at: Mapped[time] = mapped_column(Time, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)

    restaurant = relationship("Restaurant")
