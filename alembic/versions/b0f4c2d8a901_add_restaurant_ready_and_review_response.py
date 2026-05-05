"""add restaurant ready timestamp and review response text

Revision ID: b0f4c2d8a901
Revises: 91fe9227909f
Create Date: 2026-05-04 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b0f4c2d8a901"
down_revision: Union[str, None] = "91fe9227909f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("reviews", schema=None) as batch_op:
        batch_op.add_column(sa.Column("response_text", sa.String(length=500), nullable=True))

    with op.batch_alter_table("restaurant_offers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("reviews", schema=None) as batch_op:
        batch_op.drop_column("response_text")

    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_column("ready_at")

    with op.batch_alter_table("restaurant_offers", schema=None) as batch_op:
        batch_op.drop_column("created_at")
