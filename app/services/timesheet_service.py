import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.auth import User
from app.models.employee import Employee
from app.models.project import Project
from app.models.timesheet import Timesheet, TimesheetEntry
from app.schemas.timesheet import (
    AssignedProjectResponse,
    TimesheetCreateOrUpdate,
    TimesheetEmployeeResponse,
    TimesheetEntryInput,
    TimesheetEntryResponse,
    TimesheetRejectRequest,
    TimesheetResponse,
    TimesheetSummaryResponse,
)

DAILY_MAX_HOURS = Decimal("8.00")
PERMISSION_DENIED = "You do not have permission to perform this action."


class TimesheetService:
    def __init__(self, db: Session):
        self.db = db

    def list_assigned_projects(self, current_user: User, week_start: Optional[date]) -> list[AssignedProjectResponse]:
        employee = self._get_employee_for_user_or_403(current_user)
        week_end = week_start + timedelta(days=6) if week_start else None
        statement = (
            select(Project)
            .join(Project.assignees)
            .where(Employee.id == employee.id, Project.project_status == "active")
            .order_by(Project.project_name)
        )
        projects = list(self.db.scalars(statement).unique().all())
        filtered = [
            project
            for project in projects
            if self._project_overlaps_week(project, week_start, week_end)
        ]
        return [AssignedProjectResponse.model_validate(project) for project in filtered]

    def current_week(self, current_user: User) -> TimesheetResponse:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        return self.get_for_week(week_start, current_user)

    def list_timesheets(
        self,
        current_user: User,
        week_start: Optional[date],
        employee_id: Optional[uuid.UUID],
        timesheet_status: Optional[str],
    ) -> list[TimesheetResponse]:
        statement = self._base_select()
        if has_admin_role(current_user):
            if week_start is not None:
                statement = statement.where(Timesheet.week_start == week_start)
            if employee_id is not None:
                statement = statement.where(Timesheet.employee_id == employee_id)
            if timesheet_status is not None:
                statement = statement.where(Timesheet.status == timesheet_status)
        else:
            employee = self._get_employee_for_user_or_403(current_user)
            statement = statement.where(Timesheet.employee_id == employee.id)
            if week_start is not None:
                statement = statement.where(Timesheet.week_start == week_start)
            if timesheet_status is not None:
                statement = statement.where(Timesheet.status == timesheet_status)
        statement = statement.order_by(Timesheet.week_start.desc(), Timesheet.created_at.desc())
        return [self._to_response(timesheet) for timesheet in self.db.scalars(statement).unique().all()]

    def summary(self, current_user: User, week_start: Optional[date]) -> TimesheetSummaryResponse:
        statement = self._base_select()
        if week_start is not None:
            statement = statement.where(Timesheet.week_start == week_start)
        timesheets = list(self.db.scalars(statement).unique().all())
        counts = {"draft": 0, "submitted": 0, "approved": 0, "rejected": 0}
        total_logged_hours = Decimal("0.00")
        for timesheet in timesheets:
            if timesheet.status in counts:
                counts[timesheet.status] += 1
            total_logged_hours += sum((entry.hours for entry in timesheet.entries), Decimal("0.00"))
        return TimesheetSummaryResponse(
            total_timesheets=len(timesheets),
            draft=counts["draft"],
            submitted=counts["submitted"],
            approved=counts["approved"],
            rejected=counts["rejected"],
            total_logged_hours=total_logged_hours,
        )

    def get_for_week(self, week_start: date, current_user: User) -> TimesheetResponse:
        self._validate_week_start(week_start)
        employee = self._get_employee_for_user_or_403(current_user)
        timesheet = self.db.scalar(
            self._base_select().where(
                Timesheet.employee_id == employee.id,
                Timesheet.week_start == week_start,
            )
        )
        if timesheet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet not found")
        return self._to_response(timesheet)

    def get_by_id(self, timesheet_id: uuid.UUID, current_user: User) -> TimesheetResponse:
        timesheet = self._get_timesheet_or_404(timesheet_id)
        self._ensure_can_view(timesheet, current_user)
        return self._to_response(timesheet)

    def save_week(self, payload: TimesheetCreateOrUpdate, current_user: User) -> TimesheetResponse:
        employee = self._get_employee_for_user_or_403(current_user)
        self._ensure_not_future_week(payload.week_start)
        week_end = payload.week_start + timedelta(days=6)
        entries = self._normalize_entries(payload.entries)
        self._validate_entries(entries, employee, payload.week_start, week_end)
        timesheet = self.db.scalar(
            self._base_select().where(
                Timesheet.employee_id == employee.id,
                Timesheet.week_start == payload.week_start,
            )
        )
        if timesheet is None:
            timesheet = Timesheet(employee=employee, week_start=payload.week_start, week_end=week_end)
            self.db.add(timesheet)
            self.db.flush()
        elif timesheet.status not in {"draft", "rejected"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft or rejected timesheets can be edited",
            )
        elif timesheet.status == "rejected":
            timesheet.status = "draft"

        timesheet.week_end = week_end
        timesheet.entries.clear()
        self.db.flush()
        timesheet.entries = [
            TimesheetEntry(
                project_id=entry.project_id,
                work_date=entry.work_date,
                hours=entry.hours,
                notes=entry.notes,
            )
            for entry in entries
        ]
        try:
            self.db.commit()
            return self._to_response(self._get_timesheet_or_404(timesheet.id))
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=self._integrity_error_message(exc),
            ) from exc

    def submit(self, timesheet_id: uuid.UUID, current_user: User) -> TimesheetResponse:
        employee = self._get_employee_for_user_or_403(current_user)
        timesheet = self._get_timesheet_or_404(timesheet_id)
        self._ensure_not_future_week(timesheet.week_start)
        if timesheet.employee_id != employee.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PERMISSION_DENIED)
        if timesheet.status != "draft":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft timesheets can be submitted")
        if not timesheet.entries:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one entry is required")
        inputs = [
            TimesheetEntryInput(
                project_id=entry.project_id,
                work_date=entry.work_date,
                hours=entry.hours,
                notes=entry.notes,
            )
            for entry in timesheet.entries
        ]
        self._validate_entries(inputs, employee, timesheet.week_start, timesheet.week_end)
        timesheet.status = "submitted"
        timesheet.submitted_at = datetime.now(timezone.utc)
        self.db.commit()
        return self._to_response(self._get_timesheet_or_404(timesheet.id))

    def approve(self, timesheet_id: uuid.UUID, current_user: User) -> TimesheetResponse:
        timesheet = self._get_timesheet_or_404(timesheet_id)
        if timesheet.status != "submitted":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only submitted timesheets can be approved")
        timesheet.status = "approved"
        timesheet.approved_at = datetime.now(timezone.utc)
        timesheet.approved_by = current_user.id
        self.db.commit()
        return self._to_response(self._get_timesheet_or_404(timesheet.id))

    def reject(self, timesheet_id: uuid.UUID, payload: TimesheetRejectRequest, current_user: User) -> TimesheetResponse:
        timesheet = self._get_timesheet_or_404(timesheet_id)
        if timesheet.status != "submitted":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only submitted timesheets can be rejected")
        timesheet.status = "rejected"
        timesheet.rejected_at = datetime.now(timezone.utc)
        timesheet.rejected_by = current_user.id
        timesheet.rejection_reason = payload.reason
        self.db.commit()
        return self._to_response(self._get_timesheet_or_404(timesheet.id))

    def _base_select(self):
        return select(Timesheet).options(
            selectinload(Timesheet.employee),
            selectinload(Timesheet.entries).selectinload(TimesheetEntry.project),
        )

    def _get_timesheet_or_404(self, timesheet_id: uuid.UUID) -> Timesheet:
        timesheet = self.db.scalar(self._base_select().where(Timesheet.id == timesheet_id))
        if timesheet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet not found")
        return timesheet

    def _ensure_can_view(self, timesheet: Timesheet, user: User) -> None:
        if has_admin_role(user):
            return
        employee = self._get_employee_for_user_or_403(user)
        if timesheet.employee_id != employee.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PERMISSION_DENIED)

    def _get_employee_for_user_or_403(self, user: User) -> Employee:
        employee = self.db.scalar(select(Employee).where(Employee.email == user.email.lower()))
        if employee is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authenticated user is not linked to an employee")
        return employee

    def _validate_week_start(self, week_start: date) -> None:
        if week_start.weekday() != 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="week_start must be a Monday")

    def _ensure_not_future_week(self, week_start: date) -> None:
        today = date.today()
        current_week_start = today - timedelta(days=today.weekday())
        if week_start > current_week_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Future-week timesheets cannot be created or edited",
            )

    def _normalize_entries(self, entries: list[TimesheetEntryInput]) -> list[TimesheetEntryInput]:
        normalized: list[TimesheetEntryInput] = []
        for entry in entries:
            is_blank = (
                entry.project_id is None
                and entry.work_date is None
                and (entry.hours is None or entry.hours == 0)
                and not entry.notes
            )
            if is_blank:
                continue
            if entry.project_id is None or entry.work_date is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Project and work date are required",
                )
            if entry.hours is None or entry.hours <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Hours must be greater than zero",
                )
            normalized.append(entry)
        return normalized

    def _validate_entries(
        self,
        entries: list[TimesheetEntryInput],
        employee: Employee,
        week_start: date,
        week_end: date,
    ) -> None:
        daily_totals: dict[date, Decimal] = defaultdict(lambda: Decimal("0.00"))
        seen_project_dates: set[tuple[date, uuid.UUID]] = set()
        for entry in entries:
            assert entry.work_date is not None
            assert entry.project_id is not None
            assert entry.hours is not None
            if entry.work_date < week_start or entry.work_date > week_end:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Entry work_date must be within the selected week")
            if entry.work_date.weekday() >= 5:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Weekend entries are not allowed",
                )
            if entry.hours <= 0:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Hours must be greater than zero")
            project_date_key = (entry.work_date, entry.project_id)
            if project_date_key in seen_project_dates:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This project has already been added for this date.",
                )
            seen_project_dates.add(project_date_key)
            daily_totals[entry.work_date] += entry.hours
            self._validate_project(entry.project_id, employee, entry.work_date)

        for work_date, total in daily_totals.items():
            if total > DAILY_MAX_HOURS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "DAILY_HOURS_EXCEEDED",
                        "message": "Daily logged hours cannot exceed 8 hours.",
                        "work_date": work_date.isoformat(),
                        "total_hours": float(total),
                        "maximum_hours": 8,
                    },
                )

    def _validate_project(self, project_id: uuid.UUID, employee: Employee, work_date: date) -> Project:
        project = self.db.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project does not exist")
        if project.project_status != "active":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project is not active")
        if project.start_date and work_date < project.start_date:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Work date is before the project start date")
        if project.end_date and work_date > project.end_date:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Work date is after the project end date")
        if all(assignee.id != employee.id for assignee in project.assignees):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee is not assigned to this project")
        return project

    def _project_overlaps_week(
        self,
        project: Project,
        week_start: Optional[date],
        week_end: Optional[date],
    ) -> bool:
        if week_start is None or week_end is None:
            return True
        if project.start_date and project.start_date > week_end:
            return False
        if project.end_date and project.end_date < week_start:
            return False
        return True

    def _integrity_error_message(self, exc: IntegrityError) -> str:
        message = str(exc.orig)
        if "uq_timesheet_entries_project_date" in message:
            return "This project has already been added for this date."
        return "A timesheet already exists for this employee and week"

    def _to_response(self, timesheet: Timesheet) -> TimesheetResponse:
        approver_name = self._get_user_display_name(timesheet.approved_by)
        rejecter_name = self._get_user_display_name(timesheet.rejected_by)
        entries = [
            TimesheetEntryResponse(
                id=entry.id,
                project_id=entry.project_id,
                project_code=entry.project.project_code,
                project_name=entry.project.project_name,
                work_date=entry.work_date,
                hours=entry.hours,
                notes=entry.notes,
            )
            for entry in sorted(timesheet.entries, key=lambda item: (item.work_date, item.created_at))
        ]
        daily_totals: dict[str, Decimal] = {}
        weekly_total = Decimal("0.00")
        for entry in entries:
            key = entry.work_date.isoformat()
            daily_totals[key] = daily_totals.get(key, Decimal("0.00")) + entry.hours
            weekly_total += entry.hours
        employee = TimesheetEmployeeResponse(
            id=timesheet.employee.id,
            employee_id=timesheet.employee.employee_id,
            first_name=timesheet.employee.first_name,
            last_name=timesheet.employee.last_name,
            email=timesheet.employee.email,
        )
        return TimesheetResponse(
            id=timesheet.id,
            employee=employee,
            week_start=timesheet.week_start,
            week_end=timesheet.week_end,
            status=timesheet.status,
            submitted_at=timesheet.submitted_at,
            approved_at=timesheet.approved_at,
            approved_by=timesheet.approved_by,
            approved_by_name=approver_name,
            rejected_at=timesheet.rejected_at,
            rejected_by=timesheet.rejected_by,
            rejected_by_name=rejecter_name,
            rejection_reason=timesheet.rejection_reason,
            entries=entries,
            daily_totals=daily_totals,
            weekly_total=weekly_total,
            created_at=timesheet.created_at,
            updated_at=timesheet.updated_at,
        )

    def _get_user_display_name(self, user_id: Optional[int]) -> Optional[str]:
        if user_id is None:
            return None
        user = self.db.get(User, user_id)
        if user is None:
            return None
        return f"{user.first_name} {user.last_name}".strip() or user.email


def has_admin_role(user: User) -> bool:
    return any(role.name == "admin" for role in user.roles)
