import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import verify_api_key
from app.db.database import get_db, SessionLocal
from app.db.models import Document, DocumentStatus
from app.ingestion.parsers import extract_text, ParsingError
from app.ingestion.chunker import chunk_text
from app.ingestion.embeddings import EmbeddingProvider, EmbeddingError
from app.db.vector_store import add_chunks
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.ingestion.embeddings import get_embedding_provider, EmbeddingError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(verify_api_key)])

CONTENT_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    ext = Path(file.filename).suffix.lower()

    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(settings.allowed_extensions)}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Max is {settings.max_upload_size_mb}MB.",
        )

    doc = Document(
        filename=file.filename,
        file_path="",
        content_type=CONTENT_TYPE_MAP[ext],
        status=DocumentStatus.UPLOADED,
    )
    db.add(doc)
    db.flush()

    doc_dir = Path(settings.upload_dir) / doc.id
    doc_dir.mkdir(parents=True, exist_ok=True)
    file_path = doc_dir / file.filename
    file_path.write_bytes(contents)
    doc.file_path = str(file_path)

    db.commit()
    db.refresh(doc)

    # Return immediately — processing happens in the background. The client
    # polls GET /documents/{id} to track progress through the pipeline.
    background_tasks.add_task(process_document, doc.id, file_path, doc.content_type)

    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status.value,
        message="Document uploaded, processing in background. Poll GET /documents/{id} for status.",
    )


def process_document(document_id: str, file_path: Path, content_type: str) -> None:
    """
    Runs in the background AFTER the HTTP response has already been sent.
    Needs its own DB session — the request-scoped `get_db()` session is
    already closed by the time this runs, since the request/response cycle
    has completed.
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error("Document %s not found for background processing", document_id)
            return

        settings = get_settings()

        doc.status = DocumentStatus.PARSING
        db.commit()
        text = extract_text(file_path, content_type)
        doc.extracted_chars = len(text)

        doc.status = DocumentStatus.CHUNKING
        db.commit()
        chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)

        doc.status = DocumentStatus.EMBEDDING
        db.commit()
        embedder = get_embedding_provider()
        embeddings = [embedder.embed_document_chunk(c) for c in chunks]

        add_chunks(doc.id, chunks, embeddings, doc.filename)

        doc.status = DocumentStatus.INDEXED
        db.commit()
        logger.info("Background processing complete for document %s: %d chunks", doc.id, len(chunks))

    except (ParsingError, EmbeddingError) as exc:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED
            doc.error_message = str(exc)
            db.commit()
        logger.warning("Background processing failed for document %s: %s", document_id, exc)
    except Exception:
        logger.exception("Unexpected error during background processing of document %s", document_id)
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED
            doc.error_message = "Unexpected processing error"
            db.commit()
    finally:
        db.close()


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc