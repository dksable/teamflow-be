import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class HolidayDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_file_name: str
    stored_file_name: str
    file_extension: str
    mime_type: str
    file_size: int
    storage_provider: str
    storage_key: str
    uploaded_by: int
    uploaded_by_name: Optional[str] = None
    title: Optional[str]
    description: Optional[str]
    uploaded_at: datetime
    updated_at: datetime
