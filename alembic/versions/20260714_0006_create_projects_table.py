"""create projects table

Revision ID: 20260714_0006
Revises: 20260714_0005
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "20260714_0006"
down_revision = "20260714_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_name", sa.String(length=255), nullable=False),
        sa.Column("project_code", sa.String(length=50), nullable=False),
        sa.Column("client", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_project_code"), "projects", ["project_code"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_projects_project_code"), table_name="projects")
    op.drop_table("projects")
