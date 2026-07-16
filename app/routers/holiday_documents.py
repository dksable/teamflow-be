import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_any_role
from app.models.auth import User
from app.schemas.auth import ErrorResponse
from app.schemas.holiday_document import HolidayDocumentResponse
from app.services.holiday_document_service import HolidayDocumentService
from app.services.storage_service import get_storage_service

router = APIRouter(
    tags=["holiday-documents"],
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"model": ErrorResponse},
    },
)


@router.post(
    "",
    response_model=HolidayDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload holiday document",
    description="Save the original holiday document and metadata. Admin access is required.",
)
async def upload_holiday_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> HolidayDocumentResponse:
    content = await file.read()
    service = HolidayDocumentService(db, get_storage_service())
    return service.create_document(
        original_filename=file.filename or "holiday-document",
        mime_type=file.content_type or "application/octet-stream",
        content=content,
        current_user=admin,
    )


@router.get(
    "/latest",
    response_model=HolidayDocumentResponse,
    summary="Get latest holiday document",
    description="Return the latest uploaded holiday document.",
)
def get_latest_holiday_document(
    db: Session = Depends(get_db),
    _user: User = Depends(require_any_role("admin", "view")),
) -> HolidayDocumentResponse:
    return HolidayDocumentService(db, get_storage_service()).get_latest_document()


@router.get(
    "/{document_id}",
    response_model=HolidayDocumentResponse,
    summary="Get holiday document metadata",
)
def get_holiday_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(require_any_role("admin", "view")),
) -> HolidayDocumentResponse:
    return HolidayDocumentService(db, get_storage_service()).get_document(document_id)


@router.get(
    "/{document_id}/view",
    summary="View holiday document",
    description="Stream the original file with inline content disposition.",
)
def view_holiday_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(require_any_role("admin", "view")),
) -> FileResponse:
    service = HolidayDocumentService(db, get_storage_service())
    document = service.get_document(document_id)
    path = service.get_document_file_path(document)
    return FileResponse(
        path,
        media_type=document.mime_type,
        filename=document.original_file_name,
        content_disposition_type="inline",
    )


@router.get(
    "/{document_id}/download",
    summary="Download holiday document",
    description="Download the original uploaded file with attachment content disposition.",
)
def download_holiday_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(require_any_role("admin", "view")),
) -> FileResponse:
    service = HolidayDocumentService(db, get_storage_service())
    document = service.get_document(document_id)
    path = service.get_document_file_path(document)
    return FileResponse(
        path,
        media_type=document.mime_type,
        filename=document.original_file_name,
        content_disposition_type="attachment",
    )
