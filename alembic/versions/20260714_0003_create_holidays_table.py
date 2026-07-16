"""create holidays table

Revision ID: 20260714_0003
Revises: 20260714_0002
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "20260714_0003"
down_revision = "20260714_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "holidays",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("holiday_name", sa.String(length=255), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("holiday_type", sa.String(length=50), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_file_name", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "holiday_date",
            "holiday_name",
            "location",
            name="uq_holidays_date_name_location",
        ),
    )
    op.create_index(op.f("ix_holidays_holiday_date"), "holidays", ["holiday_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_holidays_holiday_date"), table_name="holidays")
    op.drop_table("holidays")
