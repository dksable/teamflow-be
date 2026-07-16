import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.employee import Employee
from app.models.project import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db: Session):
        self.db = db
        self.projects = ProjectRepository(db)

    def list_projects(self, current_user: User) -> list[Project]:
        if has_admin_role(current_user):
            return self.projects.list_newest_first()
        employee = self._get_employee_for_user(current_user)
        if employee is None:
            return []
        return self.projects.list_assigned_to_employee(employee.id)

    def get_project(self, project_id: uuid.UUID, current_user: User) -> Project:
        project = self._get_project_or_404(project_id)
        if not has_admin_role(current_user):
            employee = self._get_employee_for_user(current_user)
            if employee is None or all(assignee.id != employee.id for assignee in project.assignees):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to perform this action.",
                )
        return project

    def create_project(self, payload: ProjectCreate) -> Project:
        self._ensure_unique_project_code(payload.project_code, current_project_id=None)
        assignees = self._get_assignees_or_422(payload.assignee_ids)
        project = Project(
            project_code=payload.project_code,
            project_name=payload.project_name,
            project_status=payload.project_status,
            start_date=payload.start_date,
            end_date=payload.end_date,
            assignees=assignees,
        )

        try:
            created = self.projects.create(project)
            self.db.commit()
            self.db.refresh(created)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project code already exists",
            ) from exc

        return created

    def update_project(self, project_id: uuid.UUID, payload: ProjectUpdate) -> Project:
        project = self._get_project_or_404(project_id)
        updates = payload.model_dump(exclude_unset=True)

        if "project_code" in updates:
            self._ensure_unique_project_code(
                updates["project_code"],
                current_project_id=project.id,
            )

        if "end_date" in updates or "start_date" in updates:
            start_date = updates.get("start_date", project.start_date)
            end_date = updates.get("end_date", project.end_date)
            if end_date is not None and end_date < start_date:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="End date must be on or after start date",
                )

        if "assignee_ids" in updates:
            project.assignees = self._get_assignees_or_422(updates.pop("assignee_ids"))

        for field, value in updates.items():
            setattr(project, field, value)

        try:
            self.db.commit()
            self.db.refresh(project)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project code already exists",
            ) from exc

        return project

    def delete_project(self, project_id: uuid.UUID) -> None:
        project = self._get_project_or_404(project_id)
        self.projects.delete(project)
        self.db.commit()

    def _get_project_or_404(self, project_id: uuid.UUID) -> Project:
        project = self.projects.get_by_id(project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        return project

    def _ensure_unique_project_code(
        self,
        project_code: str,
        current_project_id: Optional[uuid.UUID],
    ) -> None:
        existing = self.projects.get_by_project_code(project_code)
        if existing is not None and existing.id != current_project_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project code already exists",
            )

    def _get_assignees_or_422(self, assignee_ids: list[uuid.UUID]) -> list[Employee]:
        employees = list(
            self.db.scalars(select(Employee).where(Employee.id.in_(assignee_ids))).all()
        )
        found_ids = {employee.id for employee in employees}
        missing_ids = [employee_id for employee_id in assignee_ids if employee_id not in found_ids]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="One or more selected employees do not exist",
            )
        return employees

    def _get_employee_for_user(self, user: User) -> Optional[Employee]:
        return self.db.scalar(select(Employee).where(Employee.email == user.email.lower()))


def has_admin_role(user: User) -> bool:
    return any(role.name == "admin" for role in user.roles)
