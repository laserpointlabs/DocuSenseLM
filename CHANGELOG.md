# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- [ ] Expand smoke test coverage to include additional functional areas from test plan:
  - Document ingestion automation
  - Dashboard expiring documents
  - LLM Q&A (RAG) with mocked responses
  - Template management
  - Export functionality
  - Config and prompt management
  - Settings/API key validation
  - Error handling and logging

