import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_any_role
from app.models.auth import User
from app.schemas.auth import ErrorResponse
from app.schemas.timesheet import (
    AssignedProjectResponse,
    TimesheetCreateOrUpdate,
    TimesheetRejectRequest,
    TimesheetResponse,
    TimesheetSummaryResponse,
)
from app.services.timesheet_service import TimesheetService

router = APIRouter(
    tags=["timesheets"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)


@router.get("/assigned-projects", response_model=list[AssignedProjectResponse])
def list_assigned_projects(
    week_start: Optional[date] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_role("admin", "view")),
) -> list[AssignedProjectResponse]:
    return TimesheetService(db).list_assigned_projects(user, week_start)


@router.get("/current", response_model=TimesheetResponse)
def get_current_timesheet(
    db: Session = Depends(get_db),
    user: User = Depends(require_any_role("admin", "view")),
) -> TimesheetResponse:
    return TimesheetService(db).current_week(user)


@router.get("/summary", response_model=TimesheetSummaryResponse)
def timesheet_summary(
    week_start: Optional[date] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TimesheetSummaryResponse:
    return TimesheetService(db).summary(admin, week_start)


@router.get("", response_model=list[TimesheetResponse])
def list_timesheets(
    week_start: Optional[date] = None,
    employee_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_role("admin", "view")),
) -> list[TimesheetResponse]:
    return TimesheetService(db).list_timesheets(user, week_start, employee_id, status_filter)


@router.put("/week", response_model=TimesheetResponse)
def save_week(
    payload: TimesheetCreateOrUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_role("admin", "view")),
) -> TimesheetResponse:
    return TimesheetService(db).save_week(payload, user)


@router.get("/{timesheet_id}", response_model=TimesheetResponse)
def get_timesheet(
    timesheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_role("admin", "view")),
) -> TimesheetResponse:
    return TimesheetService(db).get_by_id(timesheet_id, user)


@router.post("/{timesheet_id}/submit", response_model=TimesheetResponse)
def submit_timesheet(
    timesheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_role("admin", "view")),
) -> TimesheetResponse:
    return TimesheetService(db).submit(timesheet_id, user)


@router.post("/{timesheet_id}/approve", response_model=TimesheetResponse)
def approve_timesheet(
    timesheet_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TimesheetResponse:
    return TimesheetService(db).approve(timesheet_id, admin)


@router.post("/{timesheet_id}/reject", response_model=TimesheetResponse)
def reject_timesheet(
    timesheet_id: uuid.UUID,
    payload: TimesheetRejectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TimesheetResponse:
    return TimesheetService(db).reject(timesheet_id, payload, admin)
