"""add_role_partner_status_to_users

Revision ID: 7f0baf5f47e8
Revises: 6fe9e90967e8
Create Date: 2026-04-25 13:21:34.360147

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f0baf5f47e8'
down_revision: Union[str, None] = '6fe9e90967e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add role column with default CUSTOMER
    op.add_column(
        'users',
        sa.Column(
            'role',
            sa.String(20),
            server_default='CUSTOMER',
            nullable=False,
        )
    )
    # Add partner_status column (NULL for regular customers)
    op.add_column(
        'users',
        sa.Column(
            'partner_status',
            sa.String(20),
            nullable=True,
        )
    )
    # Add check constraint for valid role values
    op.create_check_constraint(
        'ck_users_role',
        'users',
        "role IN ('CUSTOMER','DELIVERY_PARTNER','ADMIN')",
    )
    # Add check constraint for valid partner_status values
    op.create_check_constraint(
        'ck_users_partner_status',
        'users',
        "partner_status IS NULL OR partner_status IN "
        "('PENDING_KYC','KYC_SUBMITTED','KYC_APPROVED','KYC_REJECTED','SUSPENDED','ACTIVE')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_users_partner_status', 'users', type_='check')
    op.drop_constraint('ck_users_role', 'users', type_='check')
    op.drop_column('users', 'partner_status')
    op.drop_column('users', 'role')
