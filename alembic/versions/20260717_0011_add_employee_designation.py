"""add employee designation

Revision ID: 20260717_0011
Revises: 20260715_0010
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa

revision = "20260717_0011"
down_revision = "20260715_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column(
            "designation",
            sa.String(length=100),
            server_default="Software Engineer",
            nullable=False,
        ),
    )
    op.alter_column("employees", "designation", server_default=None)


def downgrade() -> None:
    op.drop_column("employees", "designation")
