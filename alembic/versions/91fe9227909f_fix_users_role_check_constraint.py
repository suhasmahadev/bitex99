"""Fix users role check constraint

Revision ID: 91fe9227909f
Revises: 53999b354bf3
Create Date: 2026-05-04 10:33:35.840851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91fe9227909f'
down_revision: Union[str, None] = '53999b354bf3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role "
        "CHECK (role IN ('CUSTOMER', 'DELIVERY_PARTNER', 'RESTAURANT_PARTNER', 'ADMIN'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role "
        "CHECK (role IN ('CUSTOMER', 'DELIVERY_PARTNER', 'ADMIN'))"
    )
