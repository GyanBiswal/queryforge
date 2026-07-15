# Engineering Challenges

Real problems hit during development, how they were diagnosed, and what they taught. Included deliberately — a project that names its own hard problems is more credible than one that doesn't have any.

## 1. The silent race condition in local embedding inference

**Symptom:** Under normal sequential testing, everything worked. Under concurrent load (8 simultaneous requests), the server crashed entirely — connections dropped, `/health` stopped responding.

**Diagnosis:** Server logs showed the embedding model ("Loading embedding model BAAI/bge-base-en-v1.5...") being loaded **8 separate times**, once per concurrent request, despite code that was supposed to load it once via a `if _model is None` check and cache it at the class level.

**Root cause:** Classic time-of-check-to-time-of-use (TOCTOU) race. Eight threads all checked `_model is None` before any of them finished setting it, so all eight proceeded to load a full model instance simultaneously — competing for the same Apple Silicon GPU (`mps`) and exhausting resources.

**Fix:** Double-checked locking — a `threading.Lock()` around the load, with the `None` check repeated *inside* the lock, so only the first thread to acquire it actually loads the model; every other thread waits, then reuses the already-loaded instance.

**Second layer:** Fixing the load race wasn't sufficient — the crash persisted. Investigation showed PyTorch's MPS backend isn't guaranteed thread-safe for concurrent *inference* calls either, even on a single shared model instance. A second lock, serializing actual `.encode()` calls, was required to fully stabilize the system under concurrent load.

**Lesson:** A caching pattern that looks correct in single-request testing can hide a real concurrency bug that only surfaces under genuine simultaneous load — and even after fixing the obvious race, a deeper hardware/framework-level constraint can still be lurking underneath. Stress-testing concurrency explicitly, not just functionally, is what surfaced both issues.

## 2. Four different "it's not actually running the code I think it's running" bugs

Across several debugging sessions, four *structurally different* problems produced the same class of confusing symptom — the API behaving as if changes weren't applied, or as if data had vanished:

- A **zombie `uvicorn` process** left running on port 8000 silently served stale code alongside (or instead of) a freshly restarted server.
- A **forgotten Docker container** (`docker compose up` from earlier testing) was still bound to port 8000, absorbing requests into its own isolated database that the host filesystem couldn't see.
- **SQLAlchemy's `create_all()`** doesn't alter existing tables — after adding new model fields, the actual SQLite schema silently stayed stale until the DB file was dropped and recreated.
- A **manually-started server (no `--reload`)** didn't pick up a file edit that reverted a temporary rate-limit test value, producing results that looked like a bug but were actually just stale process state.

**Lesson:** All four had different root causes but the same category — verifying *which process, and which version of the code, is actually handling a request* is a distinct debugging skill from reading code for logical correctness, and it's the first thing worth checking when behavior doesn't match expectations despite the code looking right.

## 3. Provider lock-in surfaced mid-project, twice

A Gemini model (`gemini-2.5-flash`) was deprecated for new API keys mid-development, and separately, free-tier quota limits were hit during heavy testing.

**Fix:** Because the LLM layer was already built behind a `BaseLLMProvider` interface (a deliberate Phase 1 architecture decision, not a reaction to the outage), adding a second provider (Groq) and switching via one config value took a fraction of the time a tightly-coupled integration would have required.

**Lesson:** Provider abstraction for third-party AI APIs isn't speculative over-engineering — model deprecations and quota limits are a real, current operational reality, and this was validated directly rather than theoretically.

## 4. `slowapi` rate limiting silently appearing not to work

**Symptom:** A rate limit configured at 20 requests/minute allowed 25 sequential requests through with no `429` responses.

**Diagnosis:** Two compounding issues: stacking two separate `@limiter.limit(...)` decorators on one route doesn't reliably combine into one enforced limit (the documented, supported pattern is a single decorator with limits separated by `;`); and the 25 sequential `curl` requests, each carrying real network + LLM latency, took long enough in total that the per-minute window had already reset before the 21st request arrived.

**Fix:** Combined into one `@limiter.limit("20/minute;300/day")` decorator, and verified with a tight threshold (`2/minute`) and truly concurrent (backgrounded, parallel) requests rather than sequential ones — proving the limiter engages correctly once the test methodology itself was correct.

**Lesson:** A test that "doesn't show the expected failure" isn't proof the feature is broken — it can just as easily mean the test itself isn't actually exercising the failure condition.