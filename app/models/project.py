import uuid as uuid_lib
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProjectAssignee(Base):
    __tablename__ = "project_assignees"

    project_id: Mapped[uuid_lib.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    employee_id: Mapped[uuid_lib.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid_lib.uuid4,
    )
    project_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    project_name: Mapped[str] = mapped_column(String(255))
    project_status: Mapped[str] = mapped_column(String(50))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    assignees = relationship(
        "Employee",
        secondary="project_assignees",
        back_populates="assigned_projects",
        lazy="selectin",
    )
