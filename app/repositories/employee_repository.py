from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee


class EmployeeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_employee_id(self, employee_id: str) -> Optional[Employee]:
        statement = select(Employee).where(Employee.employee_id == employee_id)
        return self.db.scalar(statement)

    def get_by_id(self, employee_id: uuid.UUID) -> Optional[Employee]:
        return self.db.get(Employee, employee_id)

    def get_by_email(self, email: str) -> Optional[Employee]:
        statement = select(Employee).where(Employee.email == email)
        return self.db.scalar(statement)

    def list_newest_first(self) -> list[Employee]:
        statement = select(Employee).order_by(Employee.created_at.desc())
        return list(self.db.scalars(statement).all())

    def create(self, employee: Employee) -> Employee:
        self.db.add(employee)
        self.db.flush()
        self.db.refresh(employee)
        return employee

    def delete(self, employee: Employee) -> None:
        self.db.delete(employee)
        self.db.flush()
