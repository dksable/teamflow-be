from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.auth import User
from app.models.employee import Employee
from app.models.project import Project
from app.models.timesheet import Timesheet, TimesheetEntry
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    EmployeeUtilizationResponse,
    MyDashboardResponse,
    ProjectUtilizationResponse,
    RecentEmployeeResponse,
    RecentTimesheetResponse,
    UpcomingHolidayResponse,
)

EXPECTED_WEEKLY_HOURS = Decimal("40.00")


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def summary(self) -> DashboardSummaryResponse:
        return DashboardSummaryResponse(
            totalEmployees=self.db.scalar(select(func.count(Employee.id))) or 0,
            totalProjects=self.db.scalar(select(func.count(Project.id))) or 0,
            activeProjects=self.db.scalar(
                select(func.count(Project.id)).where(Project.project_status == "active")
            )
            or 0,
            pendingInvitations=self.db.scalar(
                select(func.count(User.id)).where(User.account_status == "invited")
            )
            or 0,
            pendingTimesheets=self._timesheet_status_count("submitted"),
            approvedTimesheets=self._timesheet_status_count("approved"),
            rejectedTimesheets=self._timesheet_status_count("rejected"),
        )

    def project_utilization(self) -> list[ProjectUtilizationResponse]:
        rows = self.db.execute(
            select(Project.project_name, func.coalesce(func.sum(TimesheetEntry.hours), 0))
            .outerjoin(TimesheetEntry, TimesheetEntry.project_id == Project.id)
            .group_by(Project.id, Project.project_name)
            .order_by(Project.project_name)
        ).all()
        return [
            ProjectUtilizationResponse(project=project_name, hours=Decimal(str(hours)))
            for project_name, hours in rows
        ]

    def employee_utilization(self) -> list[EmployeeUtilizationResponse]:
        employees = self.db.scalars(
            select(Employee).options(selectinload(Employee.assigned_projects)).order_by(Employee.first_name, Employee.last_name)
        ).unique().all()
        current_week_start = self._current_week_start()
        responses: list[EmployeeUtilizationResponse] = []
        for employee in employees:
            logged_hours = self._employee_week_hours(employee.id, current_week_start)
            utilization = (logged_hours / EXPECTED_WEEKLY_HOURS * Decimal("100")).quantize(Decimal("0.01"))
            responses.append(
                EmployeeUtilizationResponse(
                    employee=f"{employee.first_name} {employee.last_name}",
                    assignedProjects=len(employee.assigned_projects),
                    loggedHours=logged_hours,
                    expectedHours=EXPECTED_WEEKLY_HOURS,
                    utilization=utilization,
                    status=self._utilization_status(utilization),
                )
            )
        return responses

    def recent_timesheets(self, limit: int = 5) -> list[RecentTimesheetResponse]:
        timesheets = self.db.scalars(
            select(Timesheet)
            .options(selectinload(Timesheet.employee), selectinload(Timesheet.entries))
            .where(Timesheet.status != "draft")
            .order_by(Timesheet.submitted_at.desc().nullslast(), Timesheet.updated_at.desc())
            .limit(limit)
        ).unique().all()
        return [self._recent_timesheet_response(timesheet) for timesheet in timesheets]

    def recent_employees(self, limit: int = 5) -> list[RecentEmployeeResponse]:
        employees = self.db.scalars(
            select(Employee)
            .options(selectinload(Employee.user))
            .order_by(Employee.created_at.desc())
            .limit(limit)
        ).unique().all()
        return [
            RecentEmployeeResponse(
                name=f"{employee.first_name} {employee.last_name}",
                role=employee.role,
                status=employee.account_status,
                createdDate=employee.created_at.date(),
            )
            for employee in employees
        ]

    def upcoming_holidays(self) -> list[UpcomingHolidayResponse]:
        return []

    def my_dashboard(self, current_user: User) -> MyDashboardResponse:
        employee = self._get_employee_for_user_or_403(current_user)
        current_week_start = self._current_week_start()
        current_timesheet = self.db.scalar(
            select(Timesheet)
            .options(selectinload(Timesheet.employee), selectinload(Timesheet.entries))
            .where(Timesheet.employee_id == employee.id, Timesheet.week_start == current_week_start)
        )
        recent_timesheet = self.db.scalar(
            select(Timesheet)
            .options(selectinload(Timesheet.employee), selectinload(Timesheet.entries))
            .where(Timesheet.employee_id == employee.id, Timesheet.status != "draft")
            .order_by(Timesheet.submitted_at.desc().nullslast(), Timesheet.updated_at.desc())
            .limit(1)
        )
        return MyDashboardResponse(
            assignedProjects=len(employee.assigned_projects),
            currentWeekHours=self._employee_week_hours(employee.id, current_week_start),
            currentTimesheetStatus=current_timesheet.status if current_timesheet else None,
            recentTimesheet=self._recent_timesheet_response(recent_timesheet) if recent_timesheet else None,
            upcomingHolidays=self.upcoming_holidays(),
        )

    def _timesheet_status_count(self, status_name: str) -> int:
        return self.db.scalar(select(func.count(Timesheet.id)).where(Timesheet.status == status_name)) or 0

    def _employee_week_hours(self, employee_id, week_start: date) -> Decimal:
        total = self.db.scalar(
            select(func.coalesce(func.sum(TimesheetEntry.hours), 0))
            .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
            .where(Timesheet.employee_id == employee_id, Timesheet.week_start == week_start)
        )
        return Decimal(str(total or 0)).quantize(Decimal("0.01"))

    def _recent_timesheet_response(self, timesheet: Timesheet) -> RecentTimesheetResponse:
        total = sum((entry.hours for entry in timesheet.entries), Decimal("0.00"))
        return RecentTimesheetResponse(
            id=str(timesheet.id),
            employee=f"{timesheet.employee.first_name} {timesheet.employee.last_name}",
            week=f"{timesheet.week_start.isoformat()} - {timesheet.week_end.isoformat()}",
            hours=total,
            status=timesheet.status,
        )

    def _get_employee_for_user_or_403(self, current_user: User) -> Employee:
        employee = self.db.scalar(
            select(Employee)
            .options(selectinload(Employee.assigned_projects))
            .where(Employee.user_id == current_user.id)
        )
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No employee profile is linked to this user.",
            )
        return employee

    def _current_week_start(self) -> date:
        today = date.today()
        return today - timedelta(days=today.weekday())

    def _utilization_status(self, utilization: Decimal) -> str:
        if utilization >= Decimal("90"):
            return "green"
        if utilization >= Decimal("70"):
            return "yellow"
        return "red"
