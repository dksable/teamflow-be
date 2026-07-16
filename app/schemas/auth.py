from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["admin@teamflow.ai"])
    password: str = Field(..., min_length=1, examples=["Admin@123"])


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., examples=["<refresh-token>"])


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = Field(default=None, examples=["<refresh-token>"])


class ErrorResponse(BaseModel):
    detail: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    first_name: str
    last_name: str
    email: str
    is_active: bool
    account_status: str
    role: str
    roles: list[str]
    created_at: datetime
    updated_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    user: UserResponse


class InvitationValidationResponse(BaseModel):
    valid: bool
    email: str
    expires_at: datetime


class SetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)

    @model_validator(mode="after")
    def validate_matching_passwords(self) -> "SetPasswordRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class MessageResponse(BaseModel):
    message: str
