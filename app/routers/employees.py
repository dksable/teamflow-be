import uuid

from fastapi import APIRouter, Depends, status
from fastapi import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_any_role
from app.models.auth import User
from app.schemas.auth import ErrorResponse
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeCreateResponse,
    EmployeeResponse,
    ResendInvitationResponse,
    EmployeeUpdate,
)
from app.services.employee_service import EmployeeService

router = APIRouter(
    tags=["employees"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)


@router.post(
    "",
    response_model=EmployeeCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create employee",
    description="Create a new employee. Admin access is required.",
)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> EmployeeCreateResponse:
    return EmployeeService(db).create_employee(payload, created_by=admin)


@router.get(
    "",
    response_model=list[EmployeeResponse],
    summary="List employees",
    description="Return all employees sorted by creation date descending. Admin and view access are allowed.",
)
def list_employees(
    db: Session = Depends(get_db),
    _user: User = Depends(require_any_role("admin", "view")),
) -> list[EmployeeResponse]:
    return EmployeeService(db).list_employees()


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    summary="Update employee",
    description="Update an existing employee by internal UUID. Admin access is required.",
)
def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> EmployeeResponse:
    return EmployeeService(db).update_employee(employee_id, payload)


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete employee",
    description="Permanently delete an employee by internal UUID. Admin access is required.",
)
def delete_employee(
    employee_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> Response:
    EmployeeService(db).delete_employee(employee_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{employee_id}/resend-invitation",
    response_model=ResendInvitationResponse,
    summary="Resend employee invitation",
    description="Generate and send a new password setup invitation. Admin access is required.",
)
def resend_invitation(
    employee_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> ResendInvitationResponse:
    return EmployeeService(db).resend_invitation(employee_id, created_by=admin)
