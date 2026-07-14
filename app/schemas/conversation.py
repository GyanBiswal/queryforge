from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.schemas.query import SourceChunk


class ConversationCreateResponse(BaseModel):
    id: str
    created_at: datetime


class ConversationQueryRequest(BaseModel):
    question: str
    stream: bool = False


class ConversationTurn(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    question: str
    answer: str
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    id: str
    turns: list[ConversationTurn]