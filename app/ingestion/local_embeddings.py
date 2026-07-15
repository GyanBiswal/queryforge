import logging
import threading
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings
from app.ingestion.embeddings import BaseEmbeddingProvider, EmbeddingError

logger = logging.getLogger(__name__)
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    _model = None
    _model_lock = threading.Lock()
    _inference_lock = threading.Lock()

    def __init__(self):
        settings = get_settings()
        if LocalEmbeddingProvider._model is None:
            with LocalEmbeddingProvider._model_lock:
                if LocalEmbeddingProvider._model is None:
                    logger.info("Loading embedding model %s...", settings.embedding_model)
                    LocalEmbeddingProvider._model = SentenceTransformer(settings.embedding_model)
        self.model = LocalEmbeddingProvider._model

    def embed_document_chunk(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_query(self, text: str) -> list[float]:
        return self._embed(QUERY_INSTRUCTION + text)

    def _embed(self, text: str) -> list[float]:
        try:
            with LocalEmbeddingProvider._inference_lock:
                embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as exc:
            logger.exception("Local embedding generation failed")
            raise EmbeddingError(str(exc)) from exc