# Implementation Plan & TODO

## Guiding Objectives
- Achieve a fully functional NDA tool that runs locally/CI without external services.
- Provide deterministic, well-covered tests across unit, integration, and API flows.
- Keep dependencies injectable so we can substitute fakes during tests.

## Prioritized Workstream Backlog

### 1. Infrastructure & Dependency Injection
- [x] Introduce service registries or provider interfaces for storage, search indexers, embedding, and LLM clients. *(Service registry scaffolded; storage & search now resolved via DI.)*
- [x] Provide lightweight in-memory/NoOp implementations for tests (fake MinIO, fake OpenSearch/Qdrant, fake embedder, fake LLM). *(Implemented deterministic fakes + fixtures; continuing to expand coverage.)*
- [x] Add configuration flags/env vars to switch between real and fake services (default to real for runtime, fake for tests). *(SERVICE_PROFILE env + bootstrap wiring.)*

### 2. Ingestion Pipeline Hardening
- [x] Refactor `ingest.worker` to accept injected dependencies instead of direct imports. *(Storage, embedder, and search indexers now resolve via service registry.)*
- [x] Add unit tests for clause extraction, chunking, and metadata normalization (cover corner cases). *(Clause extractor + chunker tests added; metadata normalization still monitored during integration.)*
- [x] Write integration test covering upload → ingestion → registry using fakes.
- [x] Ensure idempotency (re-ingest same document) and duplicate file SHA detection. *(SHA256 stored on documents; idempotency + duplicate tests in `tests/integration/test_ingestion_idempotency.py`.)*

### 3. Registry Lifecycle Enhancements
- [ ] Expand tests for status transitions, duplicates, survival months, and event dedupe.
- [ ] Implement event delivery hooks (Slack/email stub) with tests verifying payload.
- [ ] Add command/job to process pending events and mark delivered (with tests).

- [x] Abstract OpenSearch/Qdrant calls behind interfaces; add in-memory search for tests. *(Backends now implement shared interface; fakes + unit tests cover indexing/search/delete.)*
- [x] Unit-test hybrid merge logic with deterministic fixtures.
- [x] Perform RAG pipeline audit (chunking, index weighting, filters) and tune for balanced keyword + semantic coverage. *(See `scripts/rag_audit.py` and `docs/rag_audit.md` for reporting guidance.)*
- [x] Integrate cross-encoder or rank fusion re-ranker to boost combined BM25 + vector results and validate via benchmarks. *(Reciprocal Rank Fusion wired into `SearchService`; tests cover output ordering.)*
- [x] Capture retrieval metrics (MRR, Recall@K) before/after tuning and publish results. *(Evaluation harness can export JSON; `eval/compare_rag.py` compares strategies.)*
- [x] Stub embedder + LLM for answer service; test context selection, deduping, and formatting. *(AnswerService unit tests now leverage fake search + LLM.)*
- [x] Integration test for question answering flow using fake search + fake LLM. *(See `tests/integration/test_answer_api.py`.)*

### 4.1 Extraction Enhancements (in progress)
- [x] Add a confidence score and “missing fields” diagnostics after the existing clause extractor. *(Metadata now carries `confidence_score` and `missing_fields`.)*
- [x] Wire in a call to a local Ollama model (e.g., `llama3:8b-instruct`) when critical fields (e.g., addresses) are missing or low confidence. *(Optional via `ENABLE_LLM_REFINEMENT`.)*
- [x] Implement structured validation on the LLM response before merging it with heuristic output. *(Responses are parsed via Pydantic; invalid JSON is discarded.)*
- [x] Update the ingest pipeline to persist `extraction_method` metadata and raw LLM output for auditing. *(Stored under `metadata.llm_refinement`.)*

### 5. API Surface & Admin Tools
- [ ] Add tests for upload endpoints (success, invalid file, failure path) using fake storage/ingestion.
- [ ] Cover `/documents`, `/admin`, `/health`, `/competency` routers.
- [ ] Validate Admin stats counting, competency CRUD, and evaluation run path.

### 6. UI Coordination (parallel with UI team)
- [ ] Expose API contract docs for UI (OpenAPI spec + examples).
- [ ] Determine testing stack (likely Jest + Playwright) and initial smoke tests.
- [ ] Provide mock API server or fixtures for UI tests.

### 7. CI & Quality Gates
- [ ] Expand GitHub Actions workflow to run unit + integration + lint (if added).
- [ ] Enforce coverage thresholds (e.g., 80% unit, targeted integration) and fail build if unmet.
- [ ] Publish test artifacts/logs for review.

### 8. LLM Support (OpenAI & Ollama)
- [ ] Add an Ollama service to `docker-compose.yml` configured with a lightweight model (e.g., `llama3:instruct` / comparable small footprint).
- [ ] Ensure API layer can switch between OpenAI (remote) and Ollama (local) via configuration.
- [ ] Provide fixtures/fakes for LLM tests while still validating provider selection logic.
- [ ] Extend tests/CI to exercise both paths: stubbed OpenAI client and local Ollama invocation (can run against a mocked endpoint during CI, real service in optional integration stage).
- [ ] Document setup instructions for running the local Ollama container alongside the stack.

- My Notes for Nice to haves
- [] Add archive capability in addition to delete so that we can maintain historical data.

## Immediate Next Steps
1. Implement dependency injection/fakes for storage, embedder, search, and LLM.
2. Update ingestion worker + upload router to use injected services.
3. Write foundational unit tests (registry edge cases, ingestion helpers) using new fakes.
4. Establish integration test for ingestion→registry pipeline.

## Coordination Notes
- UI support: confirm component/E2E harness and API expectations; request mocks if needed.
- External services: maintain ability to run against real OpenSearch/Qdrant for staging, but default CI to fakes.
