import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.auth import User, UserInvitation
from app.schemas.auth import InvitationValidationResponse, SetPasswordRequest
from app.services.email_service import EmailService, InvitationEmail


class InvitationService:
    def __init__(self, db: Session):
        self.db = db

    def create_invitation(self, user: User, created_by: Optional[int]) -> tuple[UserInvitation, str]:
        raw_token = secrets.token_urlsafe(32)
        invitation = UserInvitation(
            user=user,
            token_hash=hash_invitation_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=settings.invitation_token_expire_hours),
            created_by=created_by,
        )
        self.db.add(invitation)
        self.db.flush()
        return invitation, raw_token

    def revoke_active_invitations(self, user_id: int) -> None:
        now = datetime.now(timezone.utc)
        invitations = self.db.scalars(
            select(UserInvitation).where(
                UserInvitation.user_id == user_id,
                UserInvitation.used_at.is_(None),
                UserInvitation.revoked_at.is_(None),
            )
        ).all()
        for invitation in invitations:
            invitation.revoked_at = now

    def send_invitation_email(self, invitation: UserInvitation, raw_token: str) -> bool:
        user = invitation.user
        login_url = f"{settings.frontend_app_url.rstrip('/')}/login"
        set_password_url = f"{settings.frontend_app_url.rstrip('/')}/set-password?token={raw_token}"
        result = EmailService().send_invitation(
            InvitationEmail(
                to_email=user.email,
                first_name=user.first_name,
                login_url=login_url,
                set_password_url=set_password_url,
                expires_in_hours=settings.invitation_token_expire_hours,
            )
        )
        invitation.delivery_status = "sent" if result.sent else "failed"
        invitation.last_sent_at = datetime.now(timezone.utc)
        invitation.delivery_error = result.error
        self.db.commit()
        return result.sent

    def validate_token(self, raw_token: str) -> InvitationValidationResponse:
        invitation = self._get_valid_invitation(raw_token)
        return InvitationValidationResponse(
            valid=True,
            email=mask_email(invitation.user.email),
            expires_at=invitation.expires_at,
        )

    def set_password(self, payload: SetPasswordRequest) -> dict[str, str]:
        invitation = self._get_valid_invitation(payload.token)
        if payload.password != payload.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Passwords do not match",
            )
        validate_password_strength(payload.password)

        now = datetime.now(timezone.utc)
        user = invitation.user
        user.password_hash = hash_password(payload.password)
        user.is_active = True
        user.account_status = "active"
        invitation.used_at = now
        self.revoke_active_invitations(user.id)
        invitation.used_at = now
        self.db.commit()
        return {"message": "Password created successfully. You can now log in."}

    def _get_valid_invitation(self, raw_token: str) -> UserInvitation:
        invitation = self.db.scalar(
            select(UserInvitation).where(
                UserInvitation.token_hash == hash_invitation_token(raw_token)
            )
        )
        if invitation is None:
            raise invalid_invitation_error()
        now = datetime.now(timezone.utc)
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if invitation.used_at or invitation.revoked_at or expires_at <= now:
            raise invalid_invitation_error()
        if invitation.user.account_status == "active":
            raise invalid_invitation_error()
        return invitation


def hash_invitation_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def invalid_invitation_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This invitation link is invalid or has expired.",
    )


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def validate_password_strength(password: str) -> None:
    if (
        len(password) < 8
        or not any(char.islower() for char in password)
        or not any(char.isupper() for char in password)
        or not any(char.isdigit() for char in password)
        or not any(not char.isalnum() for char in password)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters and include uppercase, lowercase, number, and symbol.",
        )
