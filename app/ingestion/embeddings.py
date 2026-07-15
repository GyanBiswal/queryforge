from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


class BaseEmbeddingProvider(ABC):
    @abstractmethod
    def embed_document_chunk(self, text: str) -> list[float]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


def get_embedding_provider() -> BaseEmbeddingProvider:
    """
    Factory — critically, this defers importing torch/sentence-transformers
    entirely unless EMBEDDING_PROVIDER=local. On memory-constrained hosts
    (e.g. Render free tier's 512MB cap), setting EMBEDDING_PROVIDER=gemini
    avoids ever loading PyTorch into memory.
    """
    from app.core.config import get_settings
    settings = get_settings()

    if settings.embedding_provider == "gemini":
        from app.ingestion.gemini_embeddings import GeminiEmbeddingProvider
        return GeminiEmbeddingProvider()

    from app.ingestion.local_embeddings import LocalEmbeddingProvider
    return LocalEmbeddingProvider()