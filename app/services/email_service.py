from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import settings


@dataclass
class EmailResult:
    sent: bool
    error: Optional[str] = None


@dataclass
class InvitationEmail:
    to_email: str
    first_name: str
    login_url: str
    set_password_url: str
    expires_in_hours: int


class EmailService:
    def send_invitation(self, email: InvitationEmail) -> EmailResult:
        if settings.email_provider.lower() == "resend" and settings.resend_api_key:
            return self._send_resend_invitation(email)

        # Local development provider: treat as delivered without external network.
        return EmailResult(sent=True)

    def _send_resend_invitation(self, email: InvitationEmail) -> EmailResult:
        payload = {
            "from": f"{settings.email_from_name} <{settings.email_from_address}>",
            "to": [email.to_email],
            "subject": "Welcome to WorkPilot - Set up your account",
            "html": build_invitation_html(email),
            "text": build_invitation_text(email),
        }
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
                timeout=10,
            )
            if response.status_code >= 400:
                return EmailResult(
                    sent=False,
                    error=f"Email provider returned {response.status_code}: {response.text}",
                )
        except httpx.HTTPError as exc:  # pragma: no cover - external provider path
            return EmailResult(sent=False, error=str(exc))

        return EmailResult(sent=True)


def build_invitation_text(email: InvitationEmail) -> str:
    return f"""Hi {email.first_name},

Your WorkPilot account has been created.

Login email:
{email.to_email}

Please create your password using the secure link below:
{email.set_password_url}

This link will expire in {email.expires_in_hours} hours.

After setting your password, you can log in here:
{email.login_url}

Regards,
WorkPilot Team
"""


def build_invitation_html(email: InvitationEmail) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    return f"""
<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; color: #111827;">
    <h1>Welcome to WorkPilot</h1>
    <p>Hi {email.first_name},</p>
    <p>Your WorkPilot account has been created.</p>
    <p><strong>Login email:</strong><br />{email.to_email}</p>
    <p>
      <a href="{email.set_password_url}" style="display:inline-block;background:#111827;color:#ffffff;padding:12px 16px;border-radius:6px;text-decoration:none;">
        Set Your Password
      </a>
    </p>
    <p>This link will expire in {email.expires_in_hours} hours.</p>
    <p>After setting your password, you can log in here:</p>
    <p><a href="{email.login_url}">{email.login_url}</a></p>
    <p>Regards,<br />WorkPilot Team</p>
    <p style="color:#6b7280;font-size:12px;">Generated at {generated_at}</p>
  </body>
</html>
"""
