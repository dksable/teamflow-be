"""project assignments

Revision ID: 20260714_0007
Revises: 20260714_0006
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "20260714_0007"
down_revision = "20260714_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("project_status", sa.String(length=50), nullable=True))
    op.add_column(
        "projects",
        sa.Column("start_date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
    )
    op.add_column("projects", sa.Column("end_date", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE projects
        SET project_status = CASE
            WHEN status = 'Completed' THEN 'completed'
            WHEN status = 'On Hold' THEN 'on_hold'
            WHEN status = 'Cancelled' THEN 'cancelled'
            ELSE 'active'
        END
        """
    )
    op.alter_column("projects", "project_status", nullable=False)
    op.alter_column("projects", "start_date", server_default=None)
    op.drop_column("projects", "description")
    op.drop_column("projects", "client")
    op.drop_column("projects", "status")

    op.create_table(
        "project_assignees",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "employee_id"),
    )


def downgrade() -> None:
    op.drop_table("project_assignees")
    op.add_column("projects", sa.Column("status", sa.String(length=50), nullable=True))
    op.add_column("projects", sa.Column("client", sa.String(length=255), nullable=True))
    op.add_column("projects", sa.Column("description", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE projects
        SET status = CASE
            WHEN project_status = 'completed' THEN 'Completed'
            WHEN project_status = 'on_hold' THEN 'On Hold'
            WHEN project_status = 'cancelled' THEN 'Cancelled'
            ELSE 'Active'
        END,
        client = 'Internal'
        """
    )
    op.alter_column("projects", "status", nullable=False)
    op.alter_column("projects", "client", nullable=False)
    op.drop_column("projects", "end_date")
    op.drop_column("projects", "start_date")
    op.drop_column("projects", "project_status")
