# Architecture

## System overview

QueryForge has two main pipelines: **ingestion** (documents → searchable vectors) and **retrieval** (question → grounded answer).

\`\`\`mermaid
flowchart TB
    subgraph Client
        A[HTTP Client]
    end

    subgraph API["FastAPI Gateway"]
        B[Auth: API Key]
        C[Rate Limiter]
    end

    subgraph Ingestion
        D[Parse: PDF/DOCX/TXT]
        E[Chunk: sentence-aware, overlap]
        F[Embed: local BGE model]
    end

    subgraph Retrieval
        G[Embed Query]
        H[Similarity Search]
        I[Threshold Check]
        J[LLM Generation: Groq]
    end

    K[(ChromaDB<br/>vector store)]
    L[(SQLite<br/>metadata + logs)]

    A --> B --> C
    C --> D --> E --> F --> K
    F -.background task.-> L
    C --> G --> H --> K
    H --> I
    I -->|below threshold| M[Refuse: no hallucination]
    I -->|above threshold| J --> A
    J -.-> L
\`\`\`

## Ingestion pipeline

1. **Upload** (`POST /documents/upload`) — file is validated (type, size), saved to disk, a `Document` row is created with status `uploaded`. The endpoint returns immediately; processing continues via `BackgroundTasks`.
2. **Parse** — text extracted per file type (PyPDF for PDF, `python-docx` for Word, plain read for TXT). Scanned/image PDFs with no text layer are explicitly detected and flagged as failed, rather than silently indexing empty content.
3. **Chunk** — text is split into ~1000-character chunks with 150-character overlap, preferring sentence boundaries over blind character cuts. Overlap ensures facts near a chunk boundary aren't lost entirely.
4. **Embed** — each chunk is embedded via a local `sentence-transformers` model (BGE), normalized for cosine similarity.
5. **Index** — chunks + embeddings + metadata (document ID, filename, chunk index) are stored in ChromaDB.

Status progresses through `uploaded → parsing → chunking → embedding → indexed` (or `failed`), queryable via `GET /documents/{id}`.

## Retrieval pipeline

1. **Contextualize** (multi-turn only) — if conversation history exists, the question is rewritten into a standalone form via an LLM call, so retrieval isn't blind to pronouns/references from earlier turns.
2. **Embed** the (contextualized) question — using a query-specific instruction prefix, since the embedding model is trained asymmetrically for queries vs. documents.
3. **Retrieve** top-k (5) most similar chunks from ChromaDB via cosine distance.
4. **Threshold check** — chunks with distance above `0.8` are discarded. If nothing passes, the system returns an explicit refusal rather than calling the LLM at all.
5. **Generate** — remaining chunks are formatted into a numbered context block; the LLM is instructed to answer using *only* that context and cite source numbers. The original (non-contextualized) question is used for generation, so the answer's phrasing stays natural to what the user actually asked.
6. **Log** — every query, its answer, sources, and grounding status are recorded in `QueryLog` for audit/debugging.

## Provider abstraction

Both the LLM and embedding layers sit behind interfaces (`BaseLLMProvider`, `EmbeddingProvider`) so the concrete implementation is swappable via config (`LLM_PROVIDER=groq|gemini`). This isn't speculative design — it was exercised for real mid-project when a Gemini model was deprecated and again when Gemini's free-tier quota needed a fallback; both required only a config change plus one new provider class.

## Why grounding refusal, specifically

The system explicitly checks retrieval quality (similarity threshold) *before* ever calling the LLM. If nothing relevant is found, it returns a fixed "I don't know" message — it never asks the LLM to answer without context. This is deliberate: an enterprise Q&A tool that confidently answers questions its documents don't actually cover is a liability, not a feature. The trade-off is that legitimate questions phrased unusually might occasionally be refused if their embedding doesn't land close enough to relevant chunks — an accepted cost for avoiding hallucination.