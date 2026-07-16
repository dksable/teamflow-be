import re
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


email_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
allowed_roles = {"admin", "view"}


class EmployeeCreate(BaseModel):
    employee_id: str = Field(..., min_length=1, examples=["EMP-1001"])
    first_name: str = Field(..., min_length=1, examples=["Rahul"])
    last_name: str = Field(..., min_length=1, examples=["Sharma"])
    email: str = Field(..., min_length=1, examples=["rahul.sharma@teamflow.com"])
    date_of_birth: date = Field(..., examples=["1995-06-15"])
    designation: str = Field(..., min_length=1, examples=["Software Engineer"])
    role: str = Field(default="view", examples=["view"])

    @field_validator("employee_id", "first_name", "last_name", "designation", mode="before")
    @classmethod
    def trim_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not email_pattern.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in allowed_roles:
            raise ValueError("Role must be admin or view")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class EmployeeUpdate(BaseModel):
    employee_id: Optional[str] = Field(default=None, min_length=1, examples=["EMP-1001"])
    first_name: Optional[str] = Field(default=None, min_length=1, examples=["Rahul"])
    last_name: Optional[str] = Field(default=None, min_length=1, examples=["Sharma"])
    email: Optional[str] = Field(default=None, min_length=1, examples=["rahul.sharma@teamflow.com"])
    date_of_birth: Optional[date] = Field(default=None, examples=["1995-06-15"])
    designation: Optional[str] = Field(default=None, min_length=1, examples=["Software Engineer"])
    role: Optional[str] = Field(default=None, examples=["view"])

    @field_validator("employee_id", "first_name", "last_name", "designation", mode="before")
    @classmethod
    def trim_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_optional_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("role", mode="before")
    @classmethod
    def normalize_optional_role(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not email_pattern.match(value):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("role")
    @classmethod
    def validate_optional_role(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in allowed_roles:
            raise ValueError("Role must be admin or view")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_optional_date_of_birth(cls, value: Optional[date]) -> Optional[date]:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "EmployeeUpdate":
        if not self.model_fields_set or all(
            getattr(self, field_name) is None for field_name in self.model_fields_set
        ):
            raise ValueError("At least one field must be provided")
        return self


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: str
    first_name: str
    last_name: str
    email: str
    date_of_birth: date
    designation: str
    role: str
    account_status: str
    created_at: datetime
    updated_at: datetime


class EmployeeListResponse(BaseModel):
    employees: list[EmployeeResponse]


class EmployeeCreateResponse(EmployeeResponse):
    employee: EmployeeResponse
    invitation_sent: bool


class ResendInvitationResponse(BaseModel):
    message: str
    invitation_sent: bool
