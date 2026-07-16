from datetime import date
from pathlib import Path
import sys

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.auth import Role, User  # noqa: E402
from app.models.employee import Employee  # noqa: E402

VIEW_EMAIL = "view@teamflow.ai"
VIEW_PASSWORD = "View@123"
VIEW_EMPLOYEE_ID = "EMP-VIEW-001"


def get_or_create_role(db, name: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name)
        db.add(role)
        db.flush()

    return role


def seed_view_user() -> None:
    with SessionLocal() as db:
        view_role = get_or_create_role(db, "view")

        user = db.scalar(select(User).where(User.email == VIEW_EMAIL))
        if user is None:
            user = User(
                first_name="WorkPilot",
                last_name="Viewer",
                email=VIEW_EMAIL,
                password_hash=hash_password(VIEW_PASSWORD),
                is_active=True,
                account_status="active",
            )
            db.add(user)
            db.flush()
        else:
            user.is_active = True
            user.account_status = "active"

        if view_role not in user.roles:
            user.roles.append(view_role)

        employee = db.scalar(select(Employee).where(Employee.email == VIEW_EMAIL))
        if employee is None:
            employee = Employee(
                employee_id=VIEW_EMPLOYEE_ID,
                first_name="WorkPilot",
                last_name="Viewer",
                email=VIEW_EMAIL,
                date_of_birth=date(1995, 1, 1),
                role="view",
                user=user,
            )
            db.add(employee)
        else:
            employee.employee_id = employee.employee_id or VIEW_EMPLOYEE_ID
            employee.first_name = "WorkPilot"
            employee.last_name = "Viewer"
            employee.role = "view"
            employee.user = user

        db.commit()

    print(f"View user ready: {VIEW_EMAIL}")


if __name__ == "__main__":
    seed_view_user()
