"""
User ORM model — exactly per SPEC.md Section 4.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
    )
    phone: Mapped[str] = mapped_column(String(15), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), unique=True, nullable=True, index=True)
    profile_picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
    # SPEC2.md — role and partner_status (added via migration 7f0baf5f47e8)
    role: Mapped[str] = mapped_column(
        String(20), server_default=text("'CUSTOMER'"), nullable=False,
    )
    partner_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    restaurant_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # Relationships (string refs — no circular imports)
    addresses: Mapped[list["Address"]] = relationship(
        "Address", back_populates="user", lazy="selectin", cascade="all, delete-orphan",
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order", back_populates="user", lazy="noload",
    )
    reviews: Mapped[list["Review"]] = relationship(
        "Review", back_populates="user", lazy="noload",
    )
    cart_items: Mapped[list["CartItem"]] = relationship(
        "CartItem", back_populates="user", lazy="noload", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone}>"
