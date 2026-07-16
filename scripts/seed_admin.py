from pathlib import Path
import sys

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.auth import Role, User  # noqa: E402

ADMIN_EMAIL = "admin@teamflow.ai"
ADMIN_PASSWORD = "Admin@123"


def get_or_create_role(db, name: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name)
        db.add(role)
        db.flush()

    return role


def seed_admin() -> None:
    with SessionLocal() as db:
        admin_role = get_or_create_role(db, "admin")
        get_or_create_role(db, "manager")
        get_or_create_role(db, "employee")
        get_or_create_role(db, "view")

        user = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if user is None:
            user = User(
                first_name="TeamFlow",
                last_name="Admin",
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                is_active=True,
            )
            db.add(user)

        if admin_role not in user.roles:
            user.roles.append(admin_role)

        db.commit()

    print(f"Admin user ready: {ADMIN_EMAIL}")


if __name__ == "__main__":
    seed_admin()
