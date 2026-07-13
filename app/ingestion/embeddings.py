import logging
from google import genai
from google.genai import types

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


class EmbeddingProvider:
    """
    Wraps the embedding model behind a simple interface, mirroring the
    swappable-provider pattern we're using for the LLM. If we ever move to
    a local sentence-transformers model, only this class changes.
    """

    def __init__(self):
        settings = get_settings()
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    def embed_document_chunk(self, text: str) -> list[float]:
        return self._embed(text, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, task_type="RETRIEVAL_QUERY")

    def _embed(self, text: str, task_type: str) -> list[float]:
        try:
            result = self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.dimensions,
                ),
            )
            return result.embeddings[0].values
        except Exception as exc:
            logger.exception("Embedding generation failed")
            raise EmbeddingError(str(exc)) from exc