import json
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import QueryLog
from app.schemas.query import QueryRequest, QueryResponse
from app.retrieval.rag_pipeline import answer_question

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def query(request: QueryRequest, db: Session = Depends(get_db)):
    result = answer_question(request.question)

    log_entry = QueryLog(
        question=request.question,
        answer=result.answer,
        sources=json.dumps([s.model_dump() for s in result.sources]),
        was_grounded=result.grounded,
    )
    db.add(log_entry)
    db.commit()

    return result