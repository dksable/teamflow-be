from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.models.auth import User
from app.schemas.auth import (
    ErrorResponse,
    InvitationValidationResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    SetPasswordRequest,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.services.invitation_service import InvitationService

router = APIRouter(
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    }
)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login",
    description="Validate credentials and return access and refresh tokens.",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    return AuthService(db).authenticate(payload.email, payload.password)


@router.post(
    "/refresh",
    response_model=LoginResponse,
    summary="Refresh access token",
    description="Validate a refresh token and issue a fresh token pair.",
)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> LoginResponse:
    return AuthService(db).refresh_access_token(payload.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="Stateless JWT logout; refresh token revocation is prepared for Redis.",
)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    AuthService(db).logout(payload.refresh_token)
    return {"message": "Logged out"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current user profile",
    description="Return the authenticated active user.",
)
def me(
    user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    return AuthService(db).user_response(user)


@router.get(
    "/invitations/validate",
    response_model=InvitationValidationResponse,
    summary="Validate invitation token",
)
def validate_invitation(
    token: str,
    db: Session = Depends(get_db),
) -> InvitationValidationResponse:
    return InvitationService(db).validate_token(token)


@router.post(
    "/invitations/set-password",
    response_model=MessageResponse,
    summary="Set invited user password",
)
def set_invitation_password(
    payload: SetPasswordRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return InvitationService(db).set_password(payload)
