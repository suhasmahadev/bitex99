import uuid
import enum
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func, text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class OrderResponseAction(str, enum.Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

class OrderResponse(Base):
    __tablename__ = "order_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)
    restaurant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[OrderResponseAction] = mapped_column(SAEnum(OrderResponseAction, name="order_response_action_enum"), nullable=False)
    preparation_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    order = relationship("Order")
    restaurant = relationship("Restaurant")
