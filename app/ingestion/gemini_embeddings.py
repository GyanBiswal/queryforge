import logging
from google import genai
from google.genai import types

from app.core.config import get_settings
from app.ingestion.embeddings import BaseEmbeddingProvider, EmbeddingError

logger = logging.getLogger(__name__)


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Hosted embedding API — used in memory-constrained deployments where
    loading PyTorch locally isn't viable (e.g. Render free tier, 512MB cap)."""

    def __init__(self):
        settings = get_settings()
        self.client = genai.Client(api_key=settings.google_api_key, vertexai=False)
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
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dimensions),
            )
            return result.embeddings[0].values
        except Exception as exc:
            logger.exception("Gemini embedding generation failed")
            raise EmbeddingError(str(exc)) from exc