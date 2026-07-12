import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import Document, DocumentStatus
from app.ingestion.parsers import extract_text, ParsingError
from app.schemas.document import DocumentResponse, DocumentUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

CONTENT_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    settings = get_settings()
    ext = Path(file.filename).suffix.lower()

    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(settings.allowed_extensions)}",
        )

    # Read into memory once to check size, then write to disk
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Max is {settings.max_upload_size_mb}MB.",
        )

    doc = Document(
        filename=file.filename,
        file_path="",  # set after we know the id
        content_type=CONTENT_TYPE_MAP[ext],
        status=DocumentStatus.UPLOADED,
    )
    db.add(doc)
    db.flush()  # populates doc.id without committing yet

    doc_dir = Path(settings.upload_dir) / doc.id
    doc_dir.mkdir(parents=True, exist_ok=True)
    file_path = doc_dir / file.filename
    file_path.write_bytes(contents)
    doc.file_path = str(file_path)

    db.commit()
    db.refresh(doc)

    # Synchronous parsing for now — becomes a background job in a later phase
    try:
        doc.status = DocumentStatus.PARSING
        db.commit()

        text = extract_text(file_path, doc.content_type)
        doc.extracted_chars = len(text)
        doc.status = DocumentStatus.PARSED
        logger.info("Parsed document %s (%d chars)", doc.id, len(text))

    except ParsingError as exc:
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(exc)
        logger.warning("Parsing failed for document %s: %s", doc.id, exc)

    db.commit()

    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status.value,
        message="Document processed" if doc.status == DocumentStatus.PARSED else doc.error_message,
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc