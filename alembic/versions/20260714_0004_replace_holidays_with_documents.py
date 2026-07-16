"""replace holidays with holiday documents

Revision ID: 20260714_0004
Revises: 20260714_0003
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "20260714_0004"
down_revision = "20260714_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f("ix_holidays_holiday_date"), table_name="holidays")
    op.drop_table("holidays")

    op.create_table(
        "holiday_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("original_file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_file_name", sa.String(length=255), nullable=False),
        sa.Column("file_extension", sa.String(length=20), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("storage_provider", sa.String(length=50), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint("stored_file_name"),
    )
    op.create_index(
        op.f("ix_holiday_documents_uploaded_at"),
        "holiday_documents",
        ["uploaded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_holiday_documents_uploaded_at"), table_name="holiday_documents")
    op.drop_table("holiday_documents")

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
