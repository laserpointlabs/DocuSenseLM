# RAG MCP Experiment Postmortem (fix/rag_expansion_complex_pdf*)

This document summarizes what we attempted in the three experiment branches:

- `fix/rag_expansion_complex_pdf`
- `fix/rag_expansion_complex_pdf_2`
- `fix/rag_expansion_complex_pdf_3`

Goal: **move RAG/OCR/LLM “backend intelligence” into separate MCP-style services** (so Electron + the primary API server wouldn’t need to directly own OCR/RAG/LLM implementation details).

## What we built

### MCP-style microservices (Python)

The branches introduced three separate services:

- **OCR service** (`python/mcp_ocr_server/main.py`): exposes OCR endpoints (PDF → text/pages, snippet classification).
- **RAG service** (`python/mcp_rag_server/main.py`): exposes `/ingest` and `/query` backed by Chroma + OpenAI embeddings.
- **LLM service** (`python/mcp_llm_server/main.py`): exposes “classify and extract” style endpoints for metadata extraction.

Each service was implemented as a small FastAPI app and also instantiated `FastMCP(...)` (i.e., “MCP named service”), but the integration path was **plain HTTP** (not stdio JSON-RPC).

### Main backend integration (python/server.py)

The main API server was modified to:

- Read environment variables like `MCP_OCR_URL`, `MCP_RAG_URL`, `MCP_LLM_URL`.
- Optionally **spawn the MCP servers as subprocesses on startup** (`MCP_START_SERVERS=1`), then health-check them.
- Replace local OCR/RAG/LLM calls with `httpx` calls to the separate services:
  - OCR pages/snippets via `MCP_OCR_URL`
  - embeddings/index + query via `MCP_RAG_URL`
  - classify/extract via `MCP_LLM_URL`

### CI attempts

The branches included a Linux CI workflow (`.github/workflows/ci.yml`) that tried to:

- start each MCP server on ports 7001/7002/7003,
- run integration tests (`tests/test_mcp_integration.py`, `tests/test_backend_mcp_integration.py`)

## What worked (in principle)

- **Separation of concerns**: OCR, indexing/query, and extraction were isolated behind HTTP endpoints.
- **Integration tests existed** that validated “upload → processed via MCP within timeout” using FastAPI’s TestClient.

## Why it didn’t work (practical blockers)

### 1) Startup reliability and process orchestration were brittle

Running multiple services means:

- port coordination,
- startup ordering,
- health checks,
- shutdown cleanup,
- and handling crashes/restarts.

This tends to be fragile on end-user Windows machines (and “silent failures” look like app hangs).

### 2) RAG service hard-required OpenAI at import/startup

`python/mcp_rag_server/main.py` required `OPENAI_API_KEY` and raised on startup if missing:

- that makes “no-key” runs fail hard,
- and breaks any attempt at CI/local testing without secrets,
- and prevents degraded-but-usable modes.

### 3) Data/paths weren’t anchored to Electron userData semantics

The RAG server used a DB path relative to the python directory (e.g. `python/chroma_db`) rather than the app’s userData dir.

That creates persistence/portability issues:

- packaged builds have different `resources` layout,
- multi-machine expectations (userData) don’t match “repo-relative” expectations,
- backups/migrations become complicated across multiple service stores.

### 4) “MCP” wasn’t actually the integration protocol

Although `FastMCP(...)` objects were instantiated, the backend integration used **HTTP FastAPI endpoints**.

So we got the complexity of microservices **without** the main benefit of MCP tooling (stdio JSON-RPC tool calls, consistent client/runtime contract, etc.).

### 5) Packaging complexity exploded

Electron already needed:

- embedded Python,
- heavy deps (Chroma, OCR),
- careful process cleanup (NSIS updater).

Splitting into 3 services made packaging/distribution and update behavior harder:

- more processes to stop/kill on update,
- more logs to correlate,
- more chances for “it works on dev, fails installed”.

## Lessons / how we’d revisit later (if we still want MCP)

If we revisit the “MCP RAG server” idea later, the minimum requirements would be:

- **Single service first** (only RAG) rather than three.
- **Use stdio MCP protocol end-to-end** (or commit to HTTP and drop the MCP framing).
- **No hard dependency on OpenAI at startup**:
  - allow boot without a key,
  - allow local embedding backends for CI (or deterministic mocks).
- **Anchor all persistence to Electron userData** (one authoritative location).
- **Explicit lifecycle management**:
  - “start once” (or packaged service binary),
  - supervised restarts,
  - structured logs,
  - clear UX when external service is unavailable.

## Outcome

These branches were exploratory and **not suitable for production** given reliability/packaging overhead. We’re deleting them and keeping the current integrated approach (embedded Python backend + in-process RAG/OCR with CI validation) as the shippable baseline.


