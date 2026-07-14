from datetime import datetime
from pydantic import BaseModel


class ApiKeyCreateRequest(BaseModel):
    label: str


class ApiKeyCreateResponse(BaseModel):
    id: str
    label: str
    api_key: str  # plaintext — shown once, never retrievable again
    created_at: datetime


class ApiKeyInfo(BaseModel):
    id: str
    label: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None