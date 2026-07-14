import logging
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# BGE models are trained with an instruction prefix for queries (not documents) —
# this is BGE's version of the asymmetric task-type distinction we had with Gemini.
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


class EmbeddingProvider:
    """
    Local embedding model — no API calls, no rate limits, no auth. Model
    weights download once from Hugging Face on first run and are cached
    locally (~/.cache/huggingface) after that.
    """

    _model = None  # loaded once per process, shared across instances

    def __init__(self):
        settings = get_settings()
        if EmbeddingProvider._model is None:
            logger.info("Loading embedding model %s (first load may take a moment)...", settings.embedding_model)
            EmbeddingProvider._model = SentenceTransformer(settings.embedding_model)
        self.model = EmbeddingProvider._model

    def embed_document_chunk(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_query(self, text: str) -> list[float]:
        return self._embed(QUERY_INSTRUCTION + text)

    def _embed(self, text: str) -> list[float]:
        try:
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as exc:
            logger.exception("Local embedding generation failed")
            raise EmbeddingError(str(exc)) from exc