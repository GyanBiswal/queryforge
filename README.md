# QueryForge

## Live demo
🔗 **https://queryforge-api.onrender.com/docs**

A production-oriented Retrieval-Augmented Generation (RAG) platform for enterprise document Q&A — upload internal documents, ask questions in natural language, get grounded answers with cited sources.

Built as a portfolio project to demonstrate real production RAG engineering: not just "call an LLM API," but grounding, retrieval refusal, swappable providers, multi-turn conversation handling, streaming, auth, and the concurrency issues that only show up under real load.

## What it does

- Upload PDF/DOCX/TXT documents — parsed, chunked, and embedded into a local vector store
- Ask questions and get answers **grounded only in your uploaded documents** — the system explicitly refuses to answer when retrieval finds nothing relevant, rather than hallucinating
- Every answer includes cited sources, traceable to the exact document chunk it came from
- Multi-turn conversations — follow-up questions like "what about its causes?" are automatically rewritten into standalone queries before retrieval
- Real-time streaming responses (Server-Sent Events)
- API-key authentication with hashed storage and revocation
- Background document processing — uploads return instantly, processing happens async
- Rate limiting per API key

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI | Async-native, automatic OpenAPI docs, strong typing via Pydantic |
| Vector store | ChromaDB (local) | Zero-cost, runs natively on Apple Silicon, cosine similarity |
| Embeddings | `sentence-transformers` (BGE, local) | No API cost, no rate limits, runs on-device |
| LLM | Groq (Llama 3.3 70B) | Free tier, fast inference, swappable via adapter pattern |
| Metadata DB | SQLite + SQLAlchemy | Simple, file-based; documented upgrade path to Postgres |
| Auth | API keys, bcrypt-hashed | Standard credential handling, revocable without redeploy |
| Containerization | Docker | ARM64-compatible, reproducible local dev |

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system diagram and design rationale.

Quick summary: documents go through an async ingestion pipeline (parse → chunk → embed → index); queries go through a retrieval pipeline (embed question → similarity search → threshold-based grounding check → LLM generation with cited sources). The LLM and embedding layers sit behind swappable provider interfaces — the system currently uses Groq for generation and a local model for embeddings, but either can be swapped via config.

## Getting started

### Prerequisites
- Python 3.12
- Docker (optional, for containerized run)
- A free [Groq API key](https://console.groq.com)
- (Optional) A free [Google Gemini API key](https://aistudio.google.com) — used as a fallback LLM provider

### Local setup

\`\`\`bash
git clone https://github.com/GyanBiswal/queryforge.git
cd queryforge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your GROQ_API_KEY (and optionally GOOGLE_API_KEY)
uvicorn app.main:app --reload
\`\`\`

### Docker

\`\`\`bash
docker compose up --build
\`\`\`

### First steps

\`\`\`bash
# Issue an API key
curl -X POST localhost:8000/admin/api-keys \\
  -H "Content-Type: application/json" \\
  -d '{"label": "my first key"}'
# save the returned api_key — shown only once

# Upload a document
curl -F "file=@yourfile.pdf" localhost:8000/documents/upload \\
  -H "X-API-Key: YOUR_KEY"

# Ask a question
curl -X POST localhost:8000/query \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: YOUR_KEY" \\
  -d '{"question": "What does this document say about X?", "stream": false}'
\`\`\`

Full interactive API docs (Swagger UI) are available at `localhost:8000/docs` once the server is running.

## Key engineering decisions

A few design choices worth calling out (full rationale in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)):

- **Grounding refusal over hallucination** — retrieval below a similarity threshold returns an explicit "I don't know" rather than letting the LLM guess from general knowledge. This is the single most important trust property for an enterprise Q&A tool.
- **Swappable LLM/embedding providers** — behind a common interface (`BaseLLMProvider`), so switching from Groq to Gemini (or adding OpenAI) is a config change, not a rewrite. This paid off directly during development when a model got deprecated mid-project.
- **Query contextualization for multi-turn RAG** — follow-up questions are rewritten into standalone queries (via LLM) before retrieval, since embedding a pronoun-dependent fragment like "what about its causes?" retrieves nothing useful on its own.
- **Background processing** — document ingestion runs via `BackgroundTasks` with its own DB session, so uploads return instantly instead of blocking on parse/embed/index.

## Known limitations

Documented honestly, not hidden:

- **`/admin/api-keys` is unauthenticated** — it's the key-issuance bootstrap mechanism; a real deployment would gate it behind a separate privileged credential or a CLI tool, not expose it over public HTTP.
- **SQLite's single-writer locking** means very high concurrent write load can produce transient errors. A production deployment at scale would move to PostgreSQL.
- **Embedding inference is serialized** via a lock — Apple Silicon's MPS backend isn't safely reentrant across threads for concurrent model inference, so embedding calls queue rather than run in parallel. A hosted embedding API wouldn't have this constraint (a real trade-off of choosing free local inference over a paid API).
- **No schema migrations** — schema changes require dropping and recreating the SQLite DB in development; a real deployment would use Alembic.
- **`BackgroundTasks` isn't a durable task queue** — if the server restarts mid-processing, an in-flight document is stuck at its last status with no automatic retry. Celery + Redis is the documented upgrade path for real horizontal scaling.
- **No conversation summarization** — history is capped at the last 5 turns; a very long conversation degrades to only recalling recent context.
- **Embedding provider differs between local dev and production** — local development uses a free, unlimited on-device model (`sentence-transformers`); the live deployment uses Gemini's hosted embedding API instead, because Render's free tier's 512MB memory limit can't fit PyTorch. This is a deliberate, environment-aware trade-off (see `EMBEDDING_PROVIDER` config) — worth knowing if comparing answer quality between local testing and the live demo, since two different embedding models are technically in play.

See [docs/ENGINEERING_CHALLENGES.md](docs/ENGINEERING_CHALLENGES.md) for the debugging stories behind several of these.

## License

MIT