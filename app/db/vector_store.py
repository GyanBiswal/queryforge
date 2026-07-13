import logging
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client = None
_collection = None


def get_chroma_collection():
    """Lazy singleton — ChromaDB client + collection, created once per process."""
    global _client, _collection
    if _collection is None:
        settings = get_settings()
        _client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name="document_chunks",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_chunks(
    document_id: str,
    chunks: list[str],
    embeddings: list[list[float]],
    filename: str,
) -> None:
    collection = get_chroma_collection()
    ids = [f"{document_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {"document_id": document_id, "filename": filename, "chunk_index": i}
        for i in range(len(chunks))
    ]
    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
    logger.info("Indexed %d chunks for document %s", len(chunks), document_id)


def query_similar(query_embedding: list[float], top_k: int = 5) -> dict:
    collection = get_chroma_collection()
    return collection.query(query_embeddings=[query_embedding], n_results=top_k)


def delete_document_chunks(document_id: str) -> None:
    collection = get_chroma_collection()
    collection.delete(where={"document_id": document_id})