import re
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import User
from app.models.holiday_document import HolidayDocument
from app.repositories.holiday_document_repository import HolidayDocumentRepository
from app.services.storage_service import StorageService

SUPPORTED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
ALLOWED_MIME_TYPES = set(SUPPORTED_EXTENSIONS.values()) | {
    "application/octet-stream",
    "text/plain",
}


class HolidayDocumentService:
    def __init__(self, db: Session, storage: StorageService):
        self.db = db
        self.storage = storage
        self.documents = HolidayDocumentRepository(db)

    def get_latest_document(self) -> HolidayDocument:
        document = self.documents.get_latest()
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Holiday document not found",
            )
        return document

    def get_document(self, document_id: uuid.UUID) -> HolidayDocument:
        document = self.documents.get_by_id(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Holiday document not found",
            )
        return document

    def create_document(
        self,
        original_filename: str,
        mime_type: str,
        content: bytes,
        current_user: User,
    ) -> HolidayDocument:
        original_file_name = sanitize_original_filename(original_filename)
        file_extension = Path(original_file_name).suffix.lower()
        validate_file(file_extension, mime_type, content)

        stored_file_name = f"{uuid.uuid4()}{file_extension}"
        storage_key = stored_file_name

        try:
            self.storage.upload_file(storage_key, content)
            document = self.documents.create(
                HolidayDocument(
                    original_file_name=original_file_name,
                    stored_file_name=stored_file_name,
                    file_extension=file_extension.lstrip("."),
                    mime_type=normalize_mime_type(file_extension, mime_type),
                    file_size=len(content),
                    storage_provider=settings.storage_provider,
                    storage_key=storage_key,
                    uploaded_by=current_user.id,
                )
            )
            self.db.commit()
            self.db.refresh(document)
            return document
        except SQLAlchemyError as exc:
            self.db.rollback()
            self.storage.delete_file(storage_key)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Holiday document upload failed",
            ) from exc

    def get_document_file_path(self, document: HolidayDocument) -> Path:
        try:
            return self.storage.open_file_path(document.storage_key)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Holiday document file not found",
            ) from exc


def sanitize_original_filename(filename: str) -> str:
    basename = Path(filename or "holiday-document").name.replace("\x00", "")
    basename = re.sub(r"[^A-Za-z0-9._ -]+", "_", basename).strip(" .")
    return basename or "holiday-document"


def validate_file(file_extension: str, mime_type: str, content: bytes) -> None:
    max_bytes = settings.max_holiday_file_size_mb * 1024 * 1024
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File must be {settings.max_holiday_file_size_mb} MB or smaller",
        )
    if file_extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    normalized_mime_type = (mime_type or "application/octet-stream").lower()
    if normalized_mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file MIME type")

    if not has_expected_signature(file_extension, content):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match the selected format",
        )


def normalize_mime_type(file_extension: str, mime_type: str) -> str:
    normalized = (mime_type or "").lower()
    if normalized in {"application/octet-stream", "text/plain", ""}:
        return SUPPORTED_EXTENSIONS[file_extension]
    return normalized


def has_expected_signature(file_extension: str, content: bytes) -> bool:
    if file_extension == ".pdf":
        return content.startswith(b"%PDF")
    if file_extension in {".docx", ".xlsx"}:
        return content.startswith(b"PK\x03\x04")
    if file_extension in {".doc", ".xls"}:
        return content.startswith(b"\xd0\xcf\x11\xe0")
    if file_extension == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if file_extension in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if file_extension == ".webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    if file_extension == ".csv":
        return b"\x00" not in content[:1024]
    return False
