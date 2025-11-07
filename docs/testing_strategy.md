# Testing Strategy

## Layers

1. **Unit Tests**
   - Pure logic; run fast and isolated.
   - Target coverage ≥ 80% for core modules.
2. **Integration Tests**
   - Exercise service boundaries with in-memory fakes.
   - Ensure workflows (upload → ingest → registry, search → answer) behave end-to-end without external services.
3. **API / E2E Tests**
   - Use FastAPI `TestClient` to mimic clients.
   - Later extend to UI-driven Playwright tests.

## Component Targets

| Component | Unit Tests | Integration Tests | Notes |
|-----------|------------|-------------------|-------|
| Registry Service | status transitions, dedupe, event scheduling | registry + fake event dispatcher | Already partially covered; expand cases. |
| Ingestion | clause parsing, chunking, metadata normalization | upload → ingest → registry (fakes) | Need dependency injection. |
| Storage | In-memory storage fake verifying read/write | Swap via DI | |
| Search Service | Merge logic, filter handling | Query flow with fake index returning deterministic docs | |
| Answer Service | Context dedupe, structured extraction | search + LLM fakes returning answer | |
| Upload Router | validation, error handling | uses fake storage + ingestion in background | |
| Documents/Admin | Response payload shape | | |
| Competency | CRUD, evaluation scoring | `TestClient` hitting endpoints | |
| Event Dispatch | scheduler job, delivery stub | integration verifying state change | |

## Tooling

- `pytest` with markers:
  - `@pytest.mark.unit`
  - `@pytest.mark.integration`
  - `@pytest.mark.e2e`
- Fixtures in `tests/conftest.py` provide fake services + dependency overrides.
- Custom `TestAppFactory` to build FastAPI app with overrides for each suite.

## LLM Provider Coverage

- Configuration-driven tests must exercise both OpenAI (remote) and Ollama (local) code paths.
- Primary unit/integration suites will rely on fakes for determinism; provider-specific tests assert correct request payloads and response handling.
- Add integration scenarios:
  - **OpenAI**: mock HTTP transport to validate headers, prompt formatting, and error handling without network calls.
  - **Ollama**: when the Docker service is present (local/dev), run a lightweight model inference; for CI, provide a mocked endpoint or optional job.
- Fixtures should toggle providers via environment variables so suites can validate both execution paths.

## Retrieval Benchmarks

- Hybrid search now exposes a reranking hook; Reciprocal Rank Fusion (RRF) is the default strategy and is covered by unit tests.
- The evaluation harness (`eval/run_eval.py`) reports Hit Rate@10, MRR, Precision/Recall@10, and latency percentiles; use the `--output` flag to capture JSON results for regressions.
- Future work: extend the harness to compare pre/post tuning runs (e.g., different rerankers or embedding models) and track deltas over time.

## Fakes / Mocks

| Interface | Fake Implementation | Purpose |
|-----------|--------------------|---------|
| StorageService | In-memory dictionary | avoid MinIO/S3 |
| Embedder | returns deterministic vectors (e.g., seeded random or token counts) | test search/answer |
| SearchIndexer / SearchBackend | simple list filter + scoring | mimic OpenSearch/Qdrant |
| LLM Client | returns templated answer and echoes contexts | deterministic QA |
| Event Dispatcher | collects payloads for assertions | verify notifications |

## Execution in CI

1. Unit tests (default markers) → run on every push.
2. Integration tests (`pytest -m 'unit or integration'`).
3. Placeholder for UI/E2E once front-end harness ready.
4. Coverage report using `pytest-cov` (to add later).

## Next Actions

- Implement DI layer + fakes.
- Tag tests appropriately.
- Update GitHub Actions workflow to install extras (Tesseract replaced by fakes) and run both unit + integration suites.
