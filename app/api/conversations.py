import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Conversation, QueryLog
from app.schemas.conversation import (
    ConversationCreateResponse,
    ConversationQueryRequest,
    ConversationHistoryResponse,
    ConversationTurn,
)
from app.schemas.query import QueryResponse
from app.retrieval.rag_pipeline import answer_question

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationCreateResponse)
def create_conversation(db: Session = Depends(get_db)):
    conv = Conversation()
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.post("/{conversation_id}/query", response_model=QueryResponse)
def query_conversation(
    conversation_id: str, request: ConversationQueryRequest, db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Pull recent turns as history for contextualization — last 5 keeps the
    # rewrite prompt small; a longer conversation would need the summarization
    # step we explicitly scoped out of this phase.
    past_logs = (
        db.query(QueryLog)
        .filter(QueryLog.conversation_id == conversation_id)
        .order_by(QueryLog.created_at.desc())
        .limit(5)
        .all()
    )
    history = [{"question": log.question, "answer": log.answer} for log in reversed(past_logs)]

    result, contextualized = answer_question(request.question, history=history)

    log_entry = QueryLog(
        conversation_id=conversation_id,
        question=request.question,
        contextualized_question=contextualized,
        answer=result.answer,
        sources=json.dumps([s.model_dump() for s in result.sources]),
        was_grounded=result.grounded,
    )
    db.add(log_entry)
    db.commit()

    return result


@router.get("/{conversation_id}", response_model=ConversationHistoryResponse)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    logs = (
        db.query(QueryLog)
        .filter(QueryLog.conversation_id == conversation_id)
        .order_by(QueryLog.created_at.asc())
        .all()
    )
    return ConversationHistoryResponse(
        id=conversation_id,
        turns=[ConversationTurn.model_validate(log) for log in logs],
    )