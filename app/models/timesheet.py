import uuid as uuid_lib
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Timesheet(Base):
    __tablename__ = "timesheets"
    __table_args__ = (
        UniqueConstraint("employee_id", "week_start", name="uq_timesheets_employee_week"),
    )

    id: Mapped[uuid_lib.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_lib.uuid4)
    employee_id: Mapped[uuid_lib.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    employee = relationship("Employee", lazy="selectin")
    entries = relationship(
        "TimesheetEntry",
        back_populates="timesheet",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TimesheetEntry(Base):
    __tablename__ = "timesheet_entries"
    __table_args__ = (
        UniqueConstraint("timesheet_id", "work_date", "project_id", name="uq_timesheet_entries_project_date"),
    )

    id: Mapped[uuid_lib.UUID] = mapped_column(Uuid, primary_key=True, default=uuid_lib.uuid4)
    timesheet_id: Mapped[uuid_lib.UUID] = mapped_column(
        ForeignKey("timesheets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid_lib.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    timesheet = relationship("Timesheet", back_populates="entries")
    project = relationship("Project", lazy="selectin")
