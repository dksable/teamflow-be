import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TIMESHEET_STATUSES = {"draft", "submitted", "approved", "rejected"}


class TimesheetEntryInput(BaseModel):
    project_id: Optional[uuid.UUID] = None
    work_date: Optional[date] = None
    hours: Optional[Decimal] = Field(default=None, le=Decimal("8"))
    notes: Optional[str] = None

    @field_validator("hours")
    @classmethod
    def quantize_hours(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is None:
            return None
        return value.quantize(Decimal("0.01"))

    @field_validator("notes", mode="before")
    @classmethod
    def trim_notes(cls, value: object) -> object:
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        return value


class TimesheetCreateOrUpdate(BaseModel):
    week_start: date
    entries: list[TimesheetEntryInput] = Field(default_factory=list)

    @field_validator("week_start")
    @classmethod
    def validate_monday(cls, value: date) -> date:
        if value.weekday() != 0:
            raise ValueError("week_start must be a Monday")
        return value

    @model_validator(mode="after")
    def validate_entries_in_week(self) -> "TimesheetCreateOrUpdate":
        week_end = self.week_start + timedelta(days=6)
        for entry in self.entries:
            if entry.work_date is None:
                continue
            if entry.work_date < self.week_start or entry.work_date > week_end:
                raise ValueError("Entry work_date must be within the selected week")
        return self


class TimesheetRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class AssignedProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_code: str
    project_name: str
    project_status: str
    start_date: date
    end_date: Optional[date]


class TimesheetEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    project_name: str
    work_date: date
    hours: Decimal
    notes: Optional[str]


class TimesheetEmployeeResponse(BaseModel):
    id: uuid.UUID
    employee_id: str
    first_name: str
    last_name: str
    email: str


class TimesheetResponse(BaseModel):
    id: uuid.UUID
    employee: TimesheetEmployeeResponse
    week_start: date
    week_end: date
    status: str
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    approved_by: Optional[int]
    approved_by_name: Optional[str] = None
    rejected_at: Optional[datetime]
    rejected_by: Optional[int]
    rejected_by_name: Optional[str] = None
    rejection_reason: Optional[str]
    entries: list[TimesheetEntryResponse]
    daily_totals: dict[str, Decimal]
    weekly_total: Decimal
    created_at: datetime
    updated_at: datetime


class TimesheetListResponse(BaseModel):
    timesheets: list[TimesheetResponse]


class TimesheetSummaryResponse(BaseModel):
    total_timesheets: int
    draft: int
    submitted: int
    approved: int
    rejected: int
    total_logged_hours: Decimal
