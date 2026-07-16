"""employee user invitations

Revision ID: 20260715_0008
Revises: 20260714_0007
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = "20260715_0008"
down_revision = "20260714_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("account_status", sa.String(length=20), server_default="active", nullable=False),
    )
    op.add_column("employees", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_employees_user_id", "employees", ["user_id"])
    op.create_foreign_key(
        "fk_employees_user_id_users",
        "employees",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "user_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_status", sa.String(length=30), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_error", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_invitations_user_id"), "user_invitations", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_invitations_token_hash"), "user_invitations", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_invitations_token_hash"), table_name="user_invitations")
    op.drop_index(op.f("ix_user_invitations_user_id"), table_name="user_invitations")
    op.drop_table("user_invitations")
    op.drop_constraint("fk_employees_user_id_users", "employees", type_="foreignkey")
    op.drop_constraint("uq_employees_user_id", "employees", type_="unique")
    op.drop_column("employees", "user_id")
    op.drop_column("users", "account_status")
