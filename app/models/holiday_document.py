import uuid as uuid_lib
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HolidayDocument(Base):
    __tablename__ = "holiday_documents"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid_lib.uuid4,
    )
    original_file_name: Mapped[str] = mapped_column(String(255))
    stored_file_name: Mapped[str] = mapped_column(String(255), unique=True)
    file_extension: Mapped[str] = mapped_column(String(20))
    mime_type: Mapped[str] = mapped_column(String(255))
    file_size: Mapped[int] = mapped_column(BigInteger)
    storage_provider: Mapped[str] = mapped_column(String(50))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def uploaded_by_name(self) -> None:
        return None
