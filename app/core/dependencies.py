from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.auth import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
PERMISSION_DENIED_MESSAGE = "You do not have permission to perform this action."


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    try:
        user_id = int(payload["sub"])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject",
        ) from exc

    user = UserRepository(db).get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active or user.account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def require_role(role_name: str) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_active_user)) -> User:
        role_names = {role.name for role in user.roles}
        if role_name not in role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=PERMISSION_DENIED_MESSAGE,
            )

        return user

    return dependency


def require_any_role(*role_names: str) -> Callable[[User], User]:
    def dependency(user: User = Depends(get_current_active_user)) -> User:
        user_role_names = {role.name for role in user.roles}
        if user_role_names.isdisjoint(role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=PERMISSION_DENIED_MESSAGE,
            )

        return user

    return dependency


def require_admin(user: User = Depends(require_role("admin"))) -> User:
    return user


def require_manager(user: User = Depends(require_role("manager"))) -> User:
    return user


def require_employee(user: User = Depends(require_role("employee"))) -> User:
    return user
