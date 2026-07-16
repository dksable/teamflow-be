"""create timesheets

Revision ID: 20260715_0009
Revises: 20260715_0008
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = "20260715_0009"
down_revision = "20260715_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "timesheets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "week_start", name="uq_timesheets_employee_week"),
    )
    op.create_index(op.f("ix_timesheets_employee_id"), "timesheets", ["employee_id"], unique=False)
    op.create_table(
        "timesheet_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timesheet_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("hours", sa.Numeric(4, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["timesheet_id"], ["timesheets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_timesheet_entries_project_id"), "timesheet_entries", ["project_id"], unique=False)
    op.create_index(op.f("ix_timesheet_entries_timesheet_id"), "timesheet_entries", ["timesheet_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_timesheet_entries_timesheet_id"), table_name="timesheet_entries")
    op.drop_index(op.f("ix_timesheet_entries_project_id"), table_name="timesheet_entries")
    op.drop_table("timesheet_entries")
    op.drop_index(op.f("ix_timesheets_employee_id"), table_name="timesheets")
    op.drop_table("timesheets")
