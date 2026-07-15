import logging
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document

logger = logging.getLogger(__name__)

DEMO_DOC_PATH = Path("app/seed_data/pollution.pdf")


def seed_demo_document(db: Session) -> None:
    """
    On Render's free tier, the filesystem (and therefore SQLite + ChromaDB)
    resets on every restart/redeploy. Rather than let a cold-started demo
    sit there with zero documents (which looks broken to anyone clicking
    the live link), automatically re-index one demo document on startup
    if none exist. Controlled via SEED_DEMO_DATA so this only runs when
    explicitly enabled (e.g. in production), not in local dev.
    """
    settings = get_settings()
    if not getattr(settings, "seed_demo_data", False):
        return

    existing = db.query(Document).count()
    if existing > 0:
        logger.info("Documents already present, skipping demo seed")
        return

    if not DEMO_DOC_PATH.exists():
        logger.warning("Demo seed file not found at %s, skipping", DEMO_DOC_PATH)
        return

    logger.info("No documents found — seeding demo document for live demo")
    from app.api.documents import process_document
    from app.db.models import DocumentStatus
    import uuid

    doc = Document(
        id=str(uuid.uuid4()),
        filename="pollution.pdf",
        file_path=str(DEMO_DOC_PATH),
        content_type="application/pdf",
        status=DocumentStatus.UPLOADED,
    )
    db.add(doc)
    db.commit()

    # Run synchronously here (not as a background task) — this happens once
    # at startup, before the app is serving traffic, so blocking briefly is fine
    # and actually preferable to a race with the first real request.
    process_document(doc.id, DEMO_DOC_PATH, doc.content_type)
    logger.info("Demo document seeded successfully")