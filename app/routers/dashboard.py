from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_any_role
from app.models.auth import User
from app.schemas.auth import ErrorResponse
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    EmployeeUtilizationResponse,
    MyDashboardResponse,
    ProjectUtilizationResponse,
    RecentEmployeeResponse,
    RecentTimesheetResponse,
    UpcomingHolidayResponse,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(
    tags=["dashboard"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    },
)


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> DashboardSummaryResponse:
    return DashboardService(db).summary()


@router.get("/project-utilization", response_model=list[ProjectUtilizationResponse])
def project_utilization(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[ProjectUtilizationResponse]:
    return DashboardService(db).project_utilization()


@router.get("/employee-utilization", response_model=list[EmployeeUtilizationResponse])
def employee_utilization(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[EmployeeUtilizationResponse]:
    return DashboardService(db).employee_utilization()


@router.get("/recent-timesheets", response_model=list[RecentTimesheetResponse])
def recent_timesheets(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[RecentTimesheetResponse]:
    return DashboardService(db).recent_timesheets()


@router.get("/recent-employees", response_model=list[RecentEmployeeResponse])
def recent_employees(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[RecentEmployeeResponse]:
    return DashboardService(db).recent_employees()


@router.get("/upcoming-holidays", response_model=list[UpcomingHolidayResponse])
def upcoming_holidays(
    db: Session = Depends(get_db),
    _user: User = Depends(require_any_role("admin", "view")),
) -> list[UpcomingHolidayResponse]:
    return DashboardService(db).upcoming_holidays()


@router.get("/me", response_model=MyDashboardResponse)
def my_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_any_role("admin", "view")),
) -> MyDashboardResponse:
    return DashboardService(db).my_dashboard(user)
