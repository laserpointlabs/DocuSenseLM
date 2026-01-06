# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **First-order product/spec docs**: Added `docs/PRD.md` and `docs/SRS.md` for scope, requirements, interfaces, and acceptance criteria
- **IPC robustness**: Preload now caches/replays `startup-status`, `python-ready`, and `python-error` so late subscribers don’t miss one-shot events

### Changed
- **Startup logging noise reduction**
  - Python: disabled Uvicorn access logs (stops `/health`/`/config`/`/documents` poll spam) and reduced default log level
  - Electron: throttled health-check logs so normal “backend booting” doesn’t look like an error storm
  - Electron dev: don’t auto-open DevTools unless `ELECTRON_OPEN_DEVTOOLS=1` (avoids noisy protocol warnings)
- **Polling**: `/documents` polling runs only when needed (Dashboard/Documents tabs) instead of continuously across all tabs

### Fixed
- **Duplicate IPC listener registration**: Preload attaches each IPC channel once and fans out to callbacks (prevents StrictMode/dev double-mount spam)
- **App stuck on LoadingScreen**: Removed a StrictMode-unsafe init guard and made startup initialization idempotent, backed by parallel health-check fallback

### Documentation
- **Roadmap tracking**: Updated `TODO.md` to reflect completed work (Windows build/install validation, threading metadata lock, bulk upload two-phase flow) and clarified remaining blockers

### Removed
- Removed a draft `docs/SDD.md` (will be re-added as a consolidated Software Design/Description document once finalized)

### Session recap (2025-12-18)
- **What you were investigating**
  - Startup console spam + lots of “errors” on launch
  - App sometimes stuck on the loading screen showing “Ready!” but never transitioning into the app
- **RAG work (where it stands)**
  - **Hybrid retrieval**: backend uses a Hybrid Search + Reciprocal Rank Fusion (RRF) strategy to combine semantic retrieval (Chroma embeddings) + keyword matching for better recall (`python/server.py`)
  - **Multi-turn stability**: UI sends prior assistant `sources` back to the backend so follow-ups stay anchored to the same document set (best-practice for multi-turn RAG) (`src/App.tsx`)
  - **Configurable retrieval knobs**: `rag.collection_name`, `rag.distance_threshold`, and `rag.max_pinned_files` in `config.default.yaml` (overridable via user config/env)
  - **Prompts**: dedicated chat prompt with explicit citation format (`SOURCES: [...]`) in `prompts.default.yaml`
  - **Diagnostics & self-heal** (already in backend):
    - `GET /rag/status` (designed to avoid “silent RAG failure”)
    - `GET /rag/debug-search` and `GET /rag/chunks` for retrieval/index inspection
    - `POST /rag/rebuild-missing` to re-index “processed but missing chunks” documents
- **What we found**
  - One-shot IPC events (`python-ready`) could be **missed by late subscribers** (LoadingScreen got it, App didn’t)
  - React 18 dev StrictMode effect behavior + an init guard caused **startup init to get cancelled** and never re-run
  - `/health` / `/config` / `/documents` polling + access logs made normal startup look like an error storm
- **What we changed (high signal)**
  - **`electron/preload.ts`**: cache + replay latest `startup-status`, `python-ready`, `python-error` to any late subscribers
  - **`src/App.tsx`**: idempotent startup init (`initializeApp`) and parallel health-check fallback so the UI never stays stuck
  - **`python/server.py`**: disabled Uvicorn access logs (`access_log=False`) so polling doesn’t flood output
  - **`electron/main.ts`**: throttled health-check logs; stopped treating all stderr as “error”; gated DevTools auto-open behind `ELECTRON_OPEN_DEVTOOLS=1`
  - **`src/App.tsx`**: `/documents` polling limited to Dashboard/Documents tabs
- **Current state**
  - Verified the app **loads into the Dashboard** after startup (no longer stuck on loading screen).
- **Where to pick up tomorrow**
  - **Verify**: cold start from `npm run dev` (no stuck loading, no noisy access-log spam)
  - **RAG hardening (MVP-critical vs handoff)**
    - **Done this session (MVP-critical, low risk)**
      - Stable hybrid fusion: replaced randomized Python `hash()` with a deterministic digest so hybrid RRF results are consistent run-to-run (`python/server.py`)
      - Safer defaults: gated verbose RAG retrieval/context/prompt logs behind `rag.debug_logging` (default off) (`python/server.py`)
      - Graceful “no index yet”: `/chat` returns a user-friendly message when Chroma has 0 chunks instead of failing or sending empty context (`python/server.py`)
      - Prompt injection guidance: prompt explicitly treats document text as untrusted (don’t follow instructions inside docs) (`prompts.default.yaml`)
    - **Handoff items (NOT required for MVP review)**
      - Quality/evals: golden set + eval harness; tune `chunk_size`/`overlap` + `rag.distance_threshold`
      - Reliability: surface `GET /rag/status` into UI; better retry/backoff messaging for OpenAI failures
      - Cost/perf: token accounting + caching/avoid re-embedding unchanged docs; cap context/retrieved chunks per query
      - Safety: stronger refusal policies + “no relevant context” handling across edge cases
  - **Auto-update system (status / next steps)**
    - **Done this session**
      - Added a basic **Help → Check for Updates…** menu entry + dialogs (packaged builds only) (`electron/main.ts`)
      - Switched packaged Windows target to include **NSIS** (required for `electron-updater`) (`package.json`)
    - **What’s still needed before it’s real**
      - Publish tagged releases to GitHub Releases (needs workflow `--publish always` + `GH_TOKEN`)
      - Test update flow end-to-end from installed NSIS build (install vX, release vX+1, verify prompt/download/restart)
  - **Triage remaining noise**:
    - Dev CSP warning (expected in dev; should be addressed for production hardening)
    - Dependency DeprecationWarnings (optional cleanup; can be muted/updated later)
  - **Docs**: re-create/finish `docs/SDD.md` as the next documentation deliverable if still desired
  - **Follow-ups (product)**: remaining MVP blockers tracked in `TODO.md` (auto-update verification, PDF viewer white screen, user-facing python-error UI, onboarding, backup/restore verification)

## [2025-12-09]

### Added
- **CI Smoke Testing Infrastructure**: Added comprehensive smoke test suite using Playwright for Electron app testing
  - Created `.github/workflows/ci-smoke.yml` workflow for automated smoke tests on Windows
  - Added `playwright.config.ts` for Playwright configuration
  - Implemented smoke tests for app startup and backend health checks (`tests/smoke/startup.spec.ts`)
  - Implemented smoke tests for document upload and status management (`tests/smoke/doc-status.spec.ts`)
  - Tests include OpenAI API mocking to avoid external dependencies during CI runs
- **Test Documentation**: Added comprehensive test plan documentation (`docs/TEST_PLAN.md`)
  - Documents functional areas and test methods
  - Outlines automation strategy for CI integration
  - Covers startup, document ingestion, status updates, dashboard, LLM Q&A, templates, export, and config management
- **Build Verification**: Added `scripts/verify-ci-artifact.ps1` script for CI artifact verification
- **Test Fixtures**: Added sample test fixture (`tests/fixtures/sample.txt`) for smoke tests

### Changed
- Updated `package.json` with smoke test script (`test:smoke`)
- Updated `.gitignore` to exclude test results and Playwright artifacts
- Updated `TODO.md` to mark CI smoke test task as completed

### Accomplishments
- ✅ Successfully implemented and integrated smoke test suite into CI pipeline
- ✅ CI workflow passes successfully on Windows runners
- ✅ Squash-merged `ci/smoke-tests` branch into `main` with clean commit history
- ✅ All changes staged, committed, and pushed to remote repository
- ✅ Branch cleanup completed (deleted locally and remotely)

### Issues Encountered
- Initial git commands required user interaction (pagers) - resolved by using non-interactive flags
- Minor formatting changes (trailing newlines) were committed during the merge process

### Open Actions / TODOs for Next Session
- [ ] Complete Windows and macOS builds (currently only Linux build completed)
- [ ] Fix issue with text areas locking up after adding API key
- [ ] Train LLM on how to use the app → add notes to RAG from training folder
- [ ] Add direct link to local storage in UI
- [ ] Save pdf markups
- [ ] Expand smoke test coverage to include additional functional areas from test plan:
  - Document ingestion automation
  - Dashboard expiring documents
  - LLM Q&A (RAG) with mocked responses
  - Template management
  - Export functionality
  - Config and prompt management
  - Settings/API key validation
  - Error handling and logging
