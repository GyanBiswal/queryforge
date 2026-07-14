import json
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import QueryLog
from app.schemas.query import QueryRequest, QueryResponse
from app.retrieval.rag_pipeline import answer_question, stream_answer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=None)
def query(request: QueryRequest, db: Session = Depends(get_db)):
    if request.stream:
        return StreamingResponse(
            _stream_and_log(request.question, db),
            media_type="text/event-stream",
        )

    result = answer_question(request.question)
    _log_query(db, request.question, result.answer, result.sources, result.grounded)
    return result


def _stream_and_log(question: str, db: Session):
    """Wraps stream_answer to also log the completed interaction once the stream finishes."""
    final_answer = ""
    final_sources = []
    final_grounded = False

    for event in stream_answer(question):
        # peek at the raw SSE string to extract the final event for logging
        if '"type": "done"' in event or '"type":"done"' in event:
            payload = json.loads(event.removeprefix("data: ").strip())
            final_answer = payload.get("answer", "")
            final_sources = payload.get("sources", [])
            final_grounded = payload.get("grounded", False)
        yield event

    _log_query(db, question, final_answer, final_sources, final_grounded)


def _log_query(db: Session, question: str, answer: str, sources, grounded: bool):
    log_entry = QueryLog(
        question=question,
        answer=answer,
        sources=json.dumps(sources if isinstance(sources, list) and sources and isinstance(sources[0], dict) else [s.model_dump() if hasattr(s, "model_dump") else s for s in sources]),
        was_grounded=grounded,
    )
    db.add(log_entry)
    db.commit()