from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str


class SourceChunk(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    grounded: bool