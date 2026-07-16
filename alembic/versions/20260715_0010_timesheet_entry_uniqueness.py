"""timesheet entry uniqueness

Revision ID: 20260715_0010
Revises: 20260715_0009
Create Date: 2026-07-15
"""

from alembic import op

revision = "20260715_0010"
down_revision = "20260715_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_timesheet_entries_project_date",
        "timesheet_entries",
        ["timesheet_id", "work_date", "project_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_timesheet_entries_project_date",
        "timesheet_entries",
        type_="unique",
    )
