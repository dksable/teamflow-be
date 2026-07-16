from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    validate_token,
    verify_password,
)
from app.models.auth import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginResponse, UserResponse
from app.services.token_blacklist import token_blacklist


class AuthService:
    def __init__(self, db: Session):
        self.users = UserRepository(db)

    def authenticate(self, email: str, password: str) -> LoginResponse:
        user = self.users.get_by_email(email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if user.account_status == "invited":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please set your password using the invitation email before logging in.",
            )

        if user.account_status == "disabled":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
            )

        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        return self._build_login_response(user)

    def refresh_access_token(self, refresh_token: str) -> LoginResponse:
        if token_blacklist.is_revoked(refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
        )

        payload = validate_token(refresh_token, "refresh")
        try:
            user_id = int(payload["sub"])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject",
            ) from exc

        user = self.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.is_active or user.account_status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        return self._build_login_response(user)

    def logout(self, refresh_token: Optional[str] = None) -> None:
        if refresh_token:
            token_blacklist.revoke(refresh_token)

    def user_response(self, user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            uuid=user.uuid,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            is_active=user.is_active,
            account_status=user.account_status,
            role=user.role,
            roles=[role.name for role in user.roles],
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def _build_login_response(self, user: User) -> LoginResponse:
        subject = str(user.id)
        return LoginResponse(
            access_token=create_access_token(subject),
            refresh_token=create_refresh_token(subject),
            user=self.user_response(user),
        )
