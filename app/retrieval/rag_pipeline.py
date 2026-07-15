import logging
from app.core.config import get_settings
from app.ingestion.embeddings import EmbeddingProvider, EmbeddingError
from app.db.vector_store import query_similar
from app.retrieval.contextualizer import contextualize_question
from app.schemas.query import SourceChunk, QueryResponse
from app.llm.provider import get_llm_provider, LLMError
import json
from typing import Iterator
from app.ingestion.embeddings import get_embedding_provider, EmbeddingError


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


def answer_question(question: str, history: list[dict] | None = None) -> tuple[QueryResponse, str]:
    """
    Returns (response, contextualized_question) — the caller needs the
    contextualized version to store in QueryLog for debugging/audit purposes.
    """
    settings = get_settings()

    contextualized = contextualize_question(question, history or [])

    embedder = get_embedding_provider()
    try:
        query_embedding = embedder.embed_query(contextualized)
    except EmbeddingError:
        logger.exception("Failed to embed query")
        return QueryResponse(answer=NO_CONTEXT_ANSWER, sources=[], grounded=False), contextualized

    results = query_similar(query_embedding, top_k=settings.retrieval_top_k)
    relevant = _filter_by_threshold(results, settings.similarity_distance_threshold)

    if not relevant:
        return QueryResponse(answer=NO_CONTEXT_ANSWER, sources=[], grounded=False), contextualized

    context, sources = _build_context(relevant)
    # Note: we prompt the LLM with the ORIGINAL question, not the contextualized one —
    # contextualization is purely a retrieval aid; the user's actual phrasing is what
    # the final answer should respond to naturally.
    prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context, question=question)

    try:
        llm = get_llm_provider()
        answer = llm.generate(prompt)
    except LLMError:
        logger.exception("Failed to generate answer")
        return QueryResponse(
            answer="Something went wrong generating an answer. Please try again.",
            sources=[], grounded=False,
        ), contextualized

    return QueryResponse(answer=answer, sources=sources, grounded=True), contextualized


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


def stream_answer(question: str) -> Iterator[str]:
    """
    SSE generator. Yields formatted 'data: ...\n\n' events:
    - a sequence of {"type": "token", "content": "..."} events as text arrives
    - one final {"type": "done", "sources": [...], "grounded": bool} event

    Retrieval happens synchronously before the first byte is sent — RAG
    requires the context before generation can even start, so there's no
    way to stream retrieval itself. The streaming only applies to generation.
    """
    settings = get_settings()
    embedder = get_embedding_provider()

    try:
        query_embedding = embedder.embed_query(question)
    except EmbeddingError:
        logger.exception("Failed to embed query")
        yield _sse_event({"type": "done", "answer": NO_CONTEXT_ANSWER, "sources": [], "grounded": False})
        return

    results = query_similar(query_embedding, top_k=settings.retrieval_top_k)
    relevant = _filter_by_threshold(results, settings.similarity_distance_threshold)

    if not relevant:
        yield _sse_event({"type": "done", "answer": NO_CONTEXT_ANSWER, "sources": [], "grounded": False})
        return

    context, sources = _build_context(relevant)
    prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context, question=question)

    full_answer = ""
    try:
        llm = get_llm_provider()
        for token in llm.stream(prompt):
            full_answer += token
            yield _sse_event({"type": "token", "content": token})
    except LLMError:
        logger.exception("Streaming generation failed")
        yield _sse_event({"type": "error", "message": "Something went wrong generating an answer."})
        return

    yield _sse_event({
        "type": "done",
        "answer": full_answer,
        "sources": [s.model_dump() for s in sources],
        "grounded": True,
    })


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"