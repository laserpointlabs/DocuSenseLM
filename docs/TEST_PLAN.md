# DocuSenseLM End-to-End Test Plan

This plan lists the core user-facing functions, how to test each locally, and how to automate them for CI once stable.

## Functional Areas & Test Methods

- **Startup & Backend**
  - Method: Launch app; verify startup status messages; health check `http://127.0.0.1:14242/health` returns `{"status":"ok"}`.
  - Automation: Headless Electron smoke (Playwright/Spectron) to assert IPC status events and health endpoint.

- **Document Ingestion**
  - Method: Upload 2–3 sample docs (PDF/DOCX). Confirm they appear in Documents list with correct titles and initial status.
  - Automation: Playwright uploads fixtures; assert list entries and status fields.

- **Document Status Updates**
  - Method: Change status (e.g., In Review → Approved). Refresh list; verify status persisted.
  - Automation: Playwright clicks status controls; reopens app state (or checks persisted metadata file) to assert status.

- **Dashboard Expiring Documents**
  - Method: Use a fixture with an expiration date soon; verify dashboard highlights expiring/expired items and counts match.
  - Automation: Seed metadata or upload fixture; Playwright asserts dashboard badge/text.

- **LLM Q&A (RAG)**
  - Method: Ask a question referencing uploaded docs; verify answer includes relevant content and sources.
  - Automation: Mock OpenAI with deterministic fixtures; Playwright sends prompt; assert response text and source chips.

- **Templates**
  - Method: Open Templates, create or use existing template, generate output; verify output file appears and content contains placeholders replaced.
  - Automation: Playwright fills template form and asserts generated file/content checksum.

- **Export**
  - Method: Export selected docs/metadata; verify exported file exists and contains expected records.
  - Automation: Playwright triggers export and validates output file (JSON/CSV) structure.

- **Config Management**
  - Method: Edit config in UI, save, restart app, verify persisted changes; use “Reset to defaults” and confirm default values applied.
  - Automation: Playwright edits config, restarts app (or reload), asserts values; then triggers reset and re-asserts defaults from `config.default.yaml`.

- **Prompt Management**
  - Method: Edit prompts, save, restart, verify prompts retained; use reset to defaults and confirm default prompts.
  - Automation: Similar to config—assert prompt text before/after reset.

- **Settings (API Key)**
  - Method: Set API key, restart app, verify key persists and that LLM calls succeed; also verify missing/invalid key shows proper error.
  - Automation: Use mocked OpenAI to assert call is made when key present and error UI when absent.

- **Logging & Errors**
  - Method: Induce a backend failure (e.g., occupy port 14242) and verify user-facing error message and log entry.
  - Automation: Start a dummy server on 14242 before app start; assert UI shows backend error.

- **Update/Version Display**
  - Method: Verify displayed version matches `package.json`.
  - Automation: Assert version text in UI equals package version.

## Local Pre-Commit Test Checklist (manual + lightweight automation)

1) Clean & build
   - `.\clean-build.ps1`
   - `npm run build:windows`
   - Launch `.\run-windows.ps1` and confirm startup messages.

2) Smoke (manual, quick)
   - Health endpoint OK.
   - Upload 1 doc, see it listed.
   - Ask one LLM question, see sources.
   - Change a status, see it persist after restart.
   - Dashboard shows expiring doc (use fixture).
   - Export once, verify file present.

3) Config/Prompts
   - Change one config value and prompt, restart, confirm persistence.
   - Reset to defaults, confirm defaults.

4) Templates
   - Generate from a template, verify output file content.

## CI Automation Plan (phased)

- **Phase 1 (Smoke)**
  - Headless Electron (Playwright) to:
    - Start app, wait for backend health.
    - Assert startup-status IPC received in renderer.
    - Assert version text matches package.json.

- **Phase 2 (Core flows)**
  - Playwright tests with fixtures:
    - Upload documents, verify list/status.
    - Dashboard expiring badge.
    - Status change persistence.
    - Export file structure validation.
  - Mock OpenAI responses for deterministic LLM Q&A assertions.

- **Phase 3 (Config/Prompts/Templates)**
  - Config edit + reset.
  - Prompt edit + reset.
  - Template generate and file validation.

- **Phase 4 (Negative/Resilience)**
  - Port-in-use failure shows user-facing error.
  - Missing/invalid API key surfaces proper UI error.

## Data/Fixtures

- Sample docs: NDA with near-expiry date, generic contract, short memo.
- Mock OpenAI responses: deterministic embeddings/chat outputs.
- Expected exports: small JSON/CSV snapshots for comparison.

## Notes

- Keep tests independent; clean user data (`%APPDATA%/DocuSenseLM`) between runs where needed.
- Prefer mocks for LLM calls in CI; allow live-key tests only in gated/staging runs.
- Use `clean-build.ps1` before local and CI runs to ensure consistency.

