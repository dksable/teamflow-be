from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.employee import Employee
from app.models.project import Project


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, project_id: uuid.UUID) -> Optional[Project]:
        statement = (
            select(Project)
            .options(selectinload(Project.assignees))
            .where(Project.id == project_id)
        )
        return self.db.scalar(statement)

    def get_by_project_code(self, project_code: str) -> Optional[Project]:
        statement = select(Project).where(Project.project_code == project_code)
        return self.db.scalar(statement)

    def list_newest_first(self) -> list[Project]:
        statement = (
            select(Project)
            .options(selectinload(Project.assignees))
            .order_by(Project.created_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def list_assigned_to_employee(self, employee_id: uuid.UUID) -> list[Project]:
        statement = (
            select(Project)
            .join(Project.assignees)
            .options(selectinload(Project.assignees))
            .where(Employee.id == employee_id)
            .order_by(Project.created_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def create(self, project: Project) -> Project:
        self.db.add(project)
        self.db.flush()
        self.db.refresh(project)
        return project

    def delete(self, project: Project) -> None:
        self.db.delete(project)
        self.db.flush()
