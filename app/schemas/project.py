import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROJECT_STATUSES = {"active", "completed", "on_hold", "cancelled"}


class ProjectAssigneeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: str
    first_name: str
    last_name: str
    email: str


class ProjectBase(BaseModel):
    project_code: str = Field(..., min_length=1, examples=["TF-001"])
    project_name: str = Field(..., min_length=1, examples=["TeamFlow"])
    project_status: str = Field(default="active", examples=["active"])
    assignee_ids: list[uuid.UUID] = Field(..., min_length=1)
    start_date: date
    end_date: Optional[date] = None

    @field_validator("project_code", "project_name", "project_status", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("project_code")
    @classmethod
    def uppercase_code(cls, value: str) -> str:
        return value.upper()

    @field_validator("project_status")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in PROJECT_STATUSES:
            raise ValueError("Project status must be active, completed, on_hold, or cancelled")
        return normalized

    @field_validator("assignee_ids")
    @classmethod
    def dedupe_assignee_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        deduped = list(dict.fromkeys(value))
        if not deduped:
            raise ValueError("At least one assignee is required")
        return deduped

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectBase":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("End date must be on or after start date")
        return self


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    project_code: Optional[str] = Field(default=None, min_length=1)
    project_name: Optional[str] = Field(default=None, min_length=1)
    project_status: Optional[str] = None
    assignee_ids: Optional[list[uuid.UUID]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @field_validator("project_code", "project_name", "project_status", mode="before")
    @classmethod
    def trim_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("project_code")
    @classmethod
    def uppercase_optional_code(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value is not None else value

    @field_validator("project_status")
    @classmethod
    def normalize_optional_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.lower()
        if normalized not in PROJECT_STATUSES:
            raise ValueError("Project status must be active, completed, on_hold, or cancelled")
        return normalized

    @field_validator("assignee_ids")
    @classmethod
    def dedupe_optional_assignee_ids(
        cls,
        value: Optional[list[uuid.UUID]],
    ) -> Optional[list[uuid.UUID]]:
        if value is None:
            return value
        deduped = list(dict.fromkeys(value))
        if not deduped:
            raise ValueError("At least one assignee is required")
        return deduped

    @model_validator(mode="after")
    def validate_update(self) -> "ProjectUpdate":
        if not self.model_fields_set or all(
            getattr(self, field_name) is None for field_name in self.model_fields_set
        ):
            raise ValueError("At least one field must be provided")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("End date must be on or after start date")
        return self


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_code: str
    project_name: str
    project_status: str
    assignees: list[ProjectAssigneeResponse]
    start_date: date
    end_date: Optional[date]
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
