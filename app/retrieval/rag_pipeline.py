import logging
from app.core.config import get_settings
from app.ingestion.embeddings import EmbeddingProvider, EmbeddingError
from app.db.vector_store import query_similar
from app.schemas.query import SourceChunk, QueryResponse
from app.llm.provider import get_llm_provider, LLMError


logger = logging.getLogger(__name__)

NO_CONTEXT_ANSWER = (
    "I couldn't find relevant information in the uploaded documents to "
    "answer this question. Try rephrasing, or check that a relevant "
    "document has been uploaded."
)

SYSTEM_PROMPT_TEMPLATE = """You are an internal knowledge assistant. Answer the \
question using ONLY the context provided below. Do not use outside knowledge.

If the context doesn't contain enough information to answer, say so explicitly \
rather than guessing.

When you use information from the context, note which source number it came from \
(e.g. "According to [Source 2], ...").

Context:
{context}

Question: {question}

Answer:"""


def answer_question(question: str) -> QueryResponse:
    settings = get_settings()
    embedder = EmbeddingProvider()

    try:
        query_embedding = embedder.embed_query(question)
    except EmbeddingError:
        logger.exception("Failed to embed query")
        return QueryResponse(answer=NO_CONTEXT_ANSWER, sources=[], grounded=False)

    results = query_similar(query_embedding, top_k=settings.retrieval_top_k)
    logger.info("Raw retrieval distances: %s", results["distances"][0])

    relevant = _filter_by_threshold(results, settings.similarity_distance_threshold)
    logger.info("Chunks passing threshold (%.2f): %d", settings.similarity_distance_threshold, len(relevant))

    if not relevant:
        return QueryResponse(answer=NO_CONTEXT_ANSWER, sources=[], grounded=False)

    context, sources = _build_context(relevant)
    prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context, question=question)

    try:
        llm = get_llm_provider()
        answer = llm.generate(prompt)
    except LLMError:
        logger.exception("Failed to generate answer")
        return QueryResponse(
            answer="Something went wrong generating an answer. Please try again.",
            sources=[],
            grounded=False,
        )

    return QueryResponse(answer=answer, sources=sources, grounded=True)


def _filter_by_threshold(results: dict, threshold: float) -> list[dict]:
    """Chroma returns parallel lists; zip and drop anything below the similarity bar."""
    docs = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    filtered = []
    for doc, meta, dist in zip(docs, metadatas, distances):
        if dist <= threshold:
            filtered.append({"text": doc, "metadata": meta, "distance": dist})
    return filtered


def _build_context(relevant: list[dict]) -> tuple[str, list[SourceChunk]]:
    context_parts = []
    sources = []
    for i, item in enumerate(relevant, start=1):
        meta = item["metadata"]
        context_parts.append(f"[Source {i}] ({meta['filename']}): {item['text']}")
        sources.append(
            SourceChunk(
                document_id=meta["document_id"],
                filename=meta["filename"],
                chunk_index=meta["chunk_index"],
                excerpt=item["text"][:200] + ("..." if len(item["text"]) > 200 else ""),
            )
        )
    return "\n\n".join(context_parts), sources