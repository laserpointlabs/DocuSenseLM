# System Audit & Testing Baseline

## Components

| Area | Key Modules | External Dependencies | Current Tests | Gaps / Notes |
|------|-------------|-----------------------|---------------|--------------|
| Ingestion Pipeline | `ingest.worker`, `ingest.parser`, `ingest.clause_extractor`, `ingest.chunker`, `ingest.embedder` | MinIO/S3, Tesseract/AWS Textract, Sentence Transformers, OpenSearch, Qdrant | None | End-to-end ingest requires network + heavy deps; need dependency injection and fixtures. |
| Storage | `api.services.storage_service` | MinIO/S3 SDKs | None | Provide test double to avoid network. |
| Registry | `api.services.registry_service`, `api.routers.registry` | Postgres features (tsvector), datetime | `tests/test_registry.py` | Need more cases (conflicts, status transitions, event delivery). |
| Search | `api.services.search_service`, `ingest/indexer_*`, `api.routers.search` | OpenSearch, Qdrant, embeddings | None | RRF reranker wired via service registry; continue to benchmark retrieval metrics and evaluate alternate rerankers. |
| Answering | `api.services.answer_service`, `llm/` | LLM provider (Ollama/OpenAI), embeddings | None | Must stub LLM, ensure context selection tested. |
| Upload / Documents | `api.routers.upload`, `api.routers.documents`, `api.services.storage_service` | MinIO, Background tasks | None | Validate happy path & error handling with stubs. |
| Admin / Health / Competency | `api.routers.admin`, `api.routers.health`, `api.routers.competency`, `api.services/db_service` | Database | None | Need unit tests for stats, competency flows. |
| UI | `ui/` Next.js | Node, APIs | No automated tests | Create plan with user for component/unit/integration coverage. |

## Critical Workflows

1. **Document Upload & Ingestion**
   1. Upload file → persisted to storage → document row created.
   2. Background ingestion parses document → chunks + metadata stored → search indexes updated → registry entry created.
2. **Registry Lifecycle**
   - Query active NDAs by counterparty / domain.
   - Schedule expiring events → deliver notifications.
3. **Discovery & Answering**
   - Hybrid search returns BM25 + vector results.
   - Answer service pulls context chunks and calls LLM.
4. **Competency Testing**
   - Manage question catalog, run evaluations, store feedback.
5. **UI End-to-End**
   - Admin uploads, Search page queries, Answer page responses, Registry/reporting views.

## Testing Gaps / Priorities

- No coverage for ingestion, search, answer, upload, competency.
- Heavy external dependencies preclude fast tests; need injectable backends/fakes.
- LLM and embeddings must be stubbed to deterministic outputs.
- UI lacks component/integration/e2e automation.

## Proposed Testing Layers

1. **Unit Tests**
   - Logic-focused modules: registry service, ingestion utilities (clause parsing), search merging, answer post-processing, competency CRUD.
2. **Integration Tests**
   - Upload → ingestion using in-memory storage + fake search/index.
   - Search/answer using stub index + stub LLM.
   - Event scheduler verifying expiry windows.
3. **End-to-End (API)**
   - API flows via FastAPI `TestClient` with fixtures to simulate entire workflow.
4. **Front-End** *(coordinate with UI team)*
   - Component tests (Jest/React Testing Library).
   - Playwright/Cypress smoke tests hitting local API.

## Immediate Next Steps

1. Introduce dependency injection layer for storage, search indexers, embedder, and LLM so tests can supply fakes.
2. Create lightweight fake implementations for unit/integration tests.
3. Expand registry tests to cover edge cases (status transitions, duplicate detection, event dedupe).
4. Add integration test orchestrating upload → ingestion → registry.
5. Define front-end testing approach with UI lead (coordinate once API path solid).
