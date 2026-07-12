import logging
from pathlib import Path

from pypdf import PdfReader
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)


class ParsingError(Exception):
    """Raised when a document's text cannot be extracted."""


def extract_text(file_path: Path, content_type: str) -> str:
    """Route to the right parser based on content type. Raises ParsingError on failure."""
    try:
        if content_type == "application/pdf":
            return _extract_pdf(file_path)
        elif content_type == "text/plain":
            return _extract_txt(file_path)
        elif content_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ):
            return _extract_docx(file_path)
        else:
            raise ParsingError(f"Unsupported content type: {content_type}")
    except ParsingError:
        raise
    except Exception as exc:
        logger.exception("Text extraction failed for %s", file_path)
        raise ParsingError(f"Failed to extract text: {exc}") from exc


def _extract_pdf(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ParsingError("No extractable text found (possibly a scanned/image PDF)")
    return text


def _extract_txt(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="replace").strip()


def _extract_docx(file_path: Path) -> str:
    doc = DocxDocument(str(file_path))
    text = "\n".join(p.text for p in doc.paragraphs).strip()
    if not text:
        raise ParsingError("No extractable text found in .docx")
    return text