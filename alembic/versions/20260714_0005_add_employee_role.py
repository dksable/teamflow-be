"""add employee role

Revision ID: 20260714_0005
Revises: 20260714_0004
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "20260714_0005"
down_revision = "20260714_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("role", sa.String(length=20), server_default="view", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("employees", "role")
