import logging
import threading
from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

logger = logging.getLogger(__name__)

QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


class EmbeddingProvider:
    _model = None
    _model_lock = threading.Lock()   # guards first-time model loading
    _inference_lock = threading.Lock()  # serializes actual encode() calls —
    # PyTorch's MPS (Apple GPU) backend is not guaranteed thread-safe for
    # concurrent inference. CPU-only backends usually tolerate this fine,
    # but on Apple Silicon this crashed the process under real concurrent
    # load in testing. Serializing here trades some throughput for stability
    # — a real, deliberate, documented limitation of local GPU inference in a
    # multi-threaded sync server, not something to code around further.

    def __init__(self):
        settings = get_settings()
        if EmbeddingProvider._model is None:
            with EmbeddingProvider._model_lock:
                if EmbeddingProvider._model is None:
                    logger.info("Loading embedding model %s...", settings.embedding_model)
                    EmbeddingProvider._model = SentenceTransformer(settings.embedding_model)
        self.model = EmbeddingProvider._model

    def embed_document_chunk(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_query(self, text: str) -> list[float]:
        return self._embed(QUERY_INSTRUCTION + text)

    def _embed(self, text: str) -> list[float]:
        try:
            with EmbeddingProvider._inference_lock:
                embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as exc:
            logger.exception("Local embedding generation failed")
            raise EmbeddingError(str(exc)) from exc