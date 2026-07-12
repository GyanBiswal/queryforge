from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str
    status: str
    extracted_chars: int
    error_message: str | None
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: str