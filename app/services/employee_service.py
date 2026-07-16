import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.auth import Role, User
from app.models.employee import Employee
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.user_repository import UserRepository
from app.schemas.employee import EmployeeCreate, EmployeeCreateResponse, EmployeeUpdate, ResendInvitationResponse
from app.services.invitation_service import InvitationService


class EmployeeService:
    def __init__(self, db: Session):
        self.db = db
        self.employees = EmployeeRepository(db)
        self.users = UserRepository(db)

    def list_employees(self) -> list[Employee]:
        return self.employees.list_newest_first()

    def create_employee(self, payload: EmployeeCreate, created_by: User) -> EmployeeCreateResponse:
        self._ensure_unique_employee_id(payload.employee_id, current_employee_id=None)
        self._ensure_unique_email(payload.email, current_employee_id=None)
        self._ensure_unique_user_email(payload.email)
        role = self._get_role_or_422(payload.role)

        user = User(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            password_hash=hash_password(uuid.uuid4().hex),
            is_active=False,
            account_status="invited",
            roles=[role],
        )
        self.db.add(user)
        self.db.flush()

        employee = Employee(
            employee_id=payload.employee_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            date_of_birth=payload.date_of_birth,
            role=payload.role,
            user=user,
        )

        try:
            created = self.employees.create(employee)
            invitation_service = InvitationService(self.db)
            invitation, raw_token = invitation_service.create_invitation(user, created_by=created_by.id)
            self.db.commit()
            self.db.refresh(created)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Employee ID or email already exists",
            ) from exc

        invitation_sent = InvitationService(self.db).send_invitation_email(invitation, raw_token)
        return EmployeeCreateResponse(
            id=created.id,
            employee_id=created.employee_id,
            first_name=created.first_name,
            last_name=created.last_name,
            email=created.email,
            date_of_birth=created.date_of_birth,
            role=created.role,
            account_status=created.account_status,
            created_at=created.created_at,
            updated_at=created.updated_at,
            employee=created,
            invitation_sent=invitation_sent,
        )

    def update_employee(self, employee_id: uuid.UUID, payload: EmployeeUpdate) -> Employee:
        employee = self._get_employee_or_404(employee_id)
        updates = payload.model_dump(exclude_none=True, exclude_unset=True)

        if "employee_id" in updates:
            self._ensure_unique_employee_id(
                updates["employee_id"],
                current_employee_id=employee.id,
            )

        if "email" in updates:
            self._ensure_unique_email(
                updates["email"],
                current_employee_id=employee.id,
            )
            self._ensure_unique_user_email(
                updates["email"],
                current_user_id=employee.user_id,
            )

        if "role" in updates:
            role = self._get_role_or_422(updates["role"])
            if employee.user is not None:
                employee.user.roles = [role]

        for field, value in updates.items():
            setattr(employee, field, value)
            if employee.user is not None and field in {"first_name", "last_name", "email"}:
                setattr(employee.user, field, value)

        try:
            self.db.commit()
            self.db.refresh(employee)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Employee ID or email already exists",
            ) from exc

        return employee

    def delete_employee(self, employee_id: uuid.UUID) -> None:
        employee = self._get_employee_or_404(employee_id)
        self.employees.delete(employee)
        self.db.commit()

    def resend_invitation(self, employee_id: uuid.UUID, created_by: User) -> ResendInvitationResponse:
        employee = self._get_employee_or_404(employee_id)
        if employee.user is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Employee does not have a linked user account",
            )
        if employee.user.account_status == "active" or employee.user.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User account is already active",
            )

        invitation_service = InvitationService(self.db)
        invitation_service.revoke_active_invitations(employee.user.id)
        invitation, raw_token = invitation_service.create_invitation(employee.user, created_by=created_by.id)
        self.db.commit()
        invitation_sent = InvitationService(self.db).send_invitation_email(invitation, raw_token)
        message = (
            "Invitation email sent successfully."
            if invitation_sent
            else "Invitation email could not be sent."
        )
        return ResendInvitationResponse(message=message, invitation_sent=invitation_sent)

    def _get_employee_or_404(self, employee_id: uuid.UUID) -> Employee:
        employee = self.employees.get_by_id(employee_id)
        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employee not found",
            )

        return employee

    def _ensure_unique_employee_id(
        self,
        employee_id: str,
        current_employee_id: Optional[uuid.UUID],
    ) -> None:
        existing = self.employees.get_by_employee_id(employee_id)
        if existing is not None and existing.id != current_employee_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Employee ID already exists",
            )

    def _ensure_unique_email(
        self,
        email: str,
        current_employee_id: Optional[uuid.UUID],
    ) -> None:
        existing = self.employees.get_by_email(email)
        if existing is not None and existing.id != current_employee_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Employee email already exists",
            )

    def _ensure_unique_user_email(
        self,
        email: str,
        current_user_id: Optional[int] = None,
    ) -> None:
        existing = self.users.get_by_email(email)
        if existing is not None and existing.id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User email already exists",
            )

    def _get_role_or_422(self, role_name: str) -> Role:
        role = self.db.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            role = Role(name=role_name)
            self.db.add(role)
            self.db.flush()
        return role
