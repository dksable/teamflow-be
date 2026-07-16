import uuid as uuid_lib
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    users: Mapped[list["User"]] = relationship(
        secondary="user_roles",
        back_populates="roles",
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(uuid_lib.uuid4()),
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    account_status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        server_default="active",
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

    roles: Mapped[list[Role]] = relationship(
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )
    employee: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        back_populates="user",
        uselist=False,
    )
    invitations: Mapped[list["UserInvitation"]] = relationship(
        "UserInvitation",
        back_populates="user",
        foreign_keys="UserInvitation.user_id",
        lazy="selectin",
    )

    @property
    def role(self) -> str:
        if any(role.name == "admin" for role in self.roles):
            return "admin"
        if any(role.name == "view" for role in self.roles):
            return "view"
        return self.roles[0].name if self.roles else "view"


class UserInvitation(Base):
    __tablename__ = "user_invitations"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid,
        default=uuid_lib.uuid4,
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    user: Mapped[User] = relationship(
        "User",
        back_populates="invitations",
        foreign_keys=[user_id],
    )
    creator: Mapped[Optional[User]] = relationship("User", foreign_keys=[created_by])
