import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.holiday_document import HolidayDocument


class HolidayDocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest(self) -> Optional[HolidayDocument]:
        statement = select(HolidayDocument).order_by(HolidayDocument.uploaded_at.desc())
        return self.db.scalar(statement.limit(1))

    def get_by_id(self, document_id: uuid.UUID) -> Optional[HolidayDocument]:
        return self.db.get(HolidayDocument, document_id)

    def create(self, document: HolidayDocument) -> HolidayDocument:
        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)
        return document
