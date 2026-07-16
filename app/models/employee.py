import uuid as uuid_lib
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid_lib.uuid4,
    )
    employee_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    date_of_birth: Mapped[date] = mapped_column(Date)
    designation: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="view", server_default="view")
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    assigned_projects = relationship(
        "Project",
        secondary="project_assignees",
        back_populates="assignees",
        lazy="selectin",
    )
    user = relationship("User", back_populates="employee", lazy="selectin")

    @property
    def account_status(self) -> str:
        if self.user is None:
            return "active"
        return self.user.account_status
