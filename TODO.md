# TODO List

---

## 🚀 MVP BLOCKERS (Must complete before release)

### Build & Distribution
- [ ] - Complete Windows build and test full installation flow
- [ ] - Test and verify auto-update mechanism works (electron-updater)
- [ ] - Create Windows installer (NSIS) - test install/update/uninstall

### Critical Bug Fixes
- [ ] - Fix PDF viewer white screen issue (periodic)
- [ ] - Chat should not lock when processing in the background
- [ ] - Add graceful error handling for Python backend crashes
- [ ] - Handle network errors gracefully (API key validation, OpenAI API failures)

### Core UX Requirements
- [ ] - Add first-run onboarding wizard (API key setup, quick start guide)
- [ ] - Fix flaky processing status when adding/reprocessing documents
- [ ] - Review and fix slow startup speed

### Testing Before Release
- [ ] - Full end-to-end testing of all core features
- [ ] - Test on clean Windows machine (no dev environment)
- [ ] - Verify backup/restore functionality works correctly

### Documentation (Minimum)
- [ ] - Create installation guide for Windows
- [ ] - Document system requirements and dependencies
- [ ] - Write quick start guide (included in app or separate doc)

---

## 📋 POST-MVP (v1.1 - Soon after initial release)

### Additional Platforms
- [ ] - Complete Mac build and test
- [ ] - Complete Linux AppImage build and test
- [ ] - Set up code signing certificates (Windows: Authenticode, Mac: Developer ID)
- [ ] - Configure Mac notarization for distribution

### Security Improvements
- [ ] - Encrypt API key storage at rest (currently plain text in config.yaml)
- [ ] - Add secure storage for credentials (OS keychain/credential manager)
- [ ] - Review and secure all API endpoints

### Enhanced Error Handling
- [ ] - Add crash reporting/error tracking (Sentry or custom)
- [ ] - Better error messages for common failures

### UI/UX Improvements
- [ ] - Add processing status to dashboard
- [ ] - Add background processing notifications with ETA
- [ ] - Add multi-delete capability (select multiple docs, delete all)
- [ ] - Add data export functionality (CSV/JSON for document metadata)
- [ ] - Implement formalized toast notification system (success, error, warning, info states with auto-dismiss and queue management)

### Documentation
- [ ] - Create installation guides for Mac/Linux
- [ ] - Create troubleshooting guide for common issues
- [ ] - Add in-app help/documentation system (F1 key, Help menu)

---

## 📅 FUTURE RELEASES (v1.2+)

### Build & Distribution
- [ ] - Build GitHub download page with release notes
- [ ] - Implement automatic updates with user notification
- [ ] - Generate release notes/changelog automatically from commits
- [ ] - Package dev system in Docker container for Cloudflare hosting

### Features & Enhancements
- [ ] - Add notes field to extracted data with edit history tracking
- [ ] - Ensure chat always has access to extracted metadata
- [ ] - Save PDF markups (Nice to have)
- [ ] - Add keyboard shortcuts reference (Help menu)

### Privacy & Compliance
- [ ] - Add privacy policy and terms of service
- [ ] - Implement data deletion/privacy controls (GDPR compliance)
- [ ] - Add privacy policy acceptance on first run
- [ ] - Audit file permissions and access controls
- [ ] - Add rate limiting for API calls

### User Experience Polish
- [ ] - Add tooltips and contextual help throughout UI
- [ ] - Create sample documents for testing/demo
- [ ] - Add accessibility features (keyboard navigation, screen reader support)
- [ ] - Test UI on different screen sizes and resolutions

### Training & Intelligence
- [ ] - Train LLM on how to use this app (RAG from training folder)
- [ ] - Verify chat history length under normal operation

### Infrastructure & DevOps
- [ ] - Set up automated release process (GitHub Actions)
- [ ] - Create release checklist template
- [ ] - Document release process and rollback procedures

---

## 🧪 TESTING & AUTOMATION (New Branch: `feature/e2e-testing`)

### Test Infrastructure Setup
- [ ] - Update playwright.config.ts with multiple test projects (smoke, e2e, api)
- [ ] - Create test output directories and reporting (HTML, JSON reports)
- [ ] - Add test result artifacts to CI workflow
- [ ] - Create shared test fixtures directory with sample documents
- [ ] - Generate test PDF/DOCX fixtures with known content for validation

### E2E Test Helpers & Utilities
- [ ] - Create `tests/helpers/electron-app.ts` - Electron app launcher with retry logic
- [ ] - Create `tests/helpers/openai-mocks.ts` - OpenAI API mocking utilities
- [ ] - Create `tests/helpers/api-client.ts` - Backend API test helpers
- [ ] - Create `tests/helpers/test-data.ts` - Test data generators and cleanup utilities
- [ ] - Create `tests/helpers/selectors.ts` - Centralized UI selectors using data-testid

### UI Automation Attributes (data-testid)
- [ ] - Add data-testid to navigation items (sidebar buttons)
- [ ] - Add data-testid to Dashboard components (cards, metrics, expiring docs)
- [ ] - Add data-testid to Documents page (upload button, search, filters, table rows)
- [ ] - Add data-testid to Chat interface (input, send button, messages, clear button)
- [ ] - Add data-testid to Settings page (API key input, config editor, backup/restore)
- [ ] - Add data-testid to all modals (upload modal, confirm dialogs, alerts)
- [ ] - Add data-testid to PDF viewer and metadata editor

### Comprehensive E2E Test Suite
- [ ] - `tests/e2e/navigation.spec.ts` - Tab navigation and sidebar tests
- [ ] - `tests/e2e/dashboard.spec.ts` - Dashboard cards, metrics, expiring documents
- [ ] - `tests/e2e/documents.spec.ts` - Upload, search, filter, archive, delete
- [ ] - `tests/e2e/document-processing.spec.ts` - Upload → process → metadata extraction
- [ ] - `tests/e2e/document-type-change.spec.ts` - Change doc type after upload
- [ ] - `tests/e2e/metadata-edit.spec.ts` - Edit extracted metadata manually
- [ ] - `tests/e2e/chat.spec.ts` - Chat with documents, clear history, sources
- [ ] - `tests/e2e/chat-rag.spec.ts` - RAG functionality with mocked OpenAI
- [ ] - `tests/e2e/settings.spec.ts` - API key management, config editor
- [ ] - `tests/e2e/backup-restore.spec.ts` - Backup download, restore from backup
- [ ] - `tests/e2e/templates.spec.ts` - Template upload and management
- [ ] - `tests/e2e/bulk-upload.spec.ts` - Multiple file upload and processing
- [ ] - `tests/e2e/error-handling.spec.ts` - Network errors, API failures, recovery

### API Integration Tests
- [ ] - `tests/api/health.spec.ts` - Backend health endpoint
- [ ] - `tests/api/documents.spec.ts` - Document CRUD operations
- [ ] - `tests/api/chat.spec.ts` - Chat endpoint with mocked LLM
- [ ] - `tests/api/config.spec.ts` - Config file read/write
- [ ] - `tests/api/backup.spec.ts` - Backup and restore endpoints
- [ ] - `tests/api/processing.spec.ts` - Document processing status

### Electron MCP Automation Improvements
- [ ] - Add window title/state for MCP detection (`DocuSenseLM - {tab}`)
- [ ] - Expose app state via IPC for MCP queries (current tab, doc count, processing status)
- [ ] - Add semantic HTML structure (landmarks, headings) for better automation
- [ ] - Add aria-labels to interactive elements
- [ ] - Create MCP-friendly status indicators (loading states, operation results)
- [ ] - Document MCP automation patterns and examples

### Browser Automation Support
- [ ] - Ensure all interactive elements are keyboard accessible
- [ ] - Add focus indicators for keyboard navigation
- [ ] - Ensure form elements have associated labels
- [ ] - Add loading/busy states that automation can detect
- [ ] - Create stable selectors (avoid dynamic class names)

### Test Documentation
- [ ] - Create `docs/TESTING.md` with test running instructions
- [ ] - Document test fixtures and how to generate them
- [ ] - Document OpenAI mocking strategies
- [ ] - Create test coverage goals and tracking
- [ ] - Document CI test workflow and failure handling

---

## ✅ COMPLETED

### Bug Fixes
- [x] - Fix the issue with locking up the text areas after adding a key
- [x] - Fix bulk drag and drop from desktop (Verified working)
- [x] - Extracted data search fixed (Hybrid search + conversation memory)
- [x] - Chat history clearing actually removes data

### Features
- [x] - Document type modification after uploading
- [x] - Manual modification of extracted information meta-data
- [x] - Add direct link to local storage
- [x] - Show/Hide status in config for dashboard display
- [x] - Bulk upload with background processing (ThreadPoolExecutor)

### UI/UX
- [x] - Document collections grouped by type with filtering
- [x] - Sort and search on document page
- [x] - Document type selection prior to drag and drop

### Testing & CI
- [x] - CI smoke test (Electron + Playwright)
- [x] - CI test for embeddable Python backend (Windows)

### Infrastructure
- [x] - Electron-mcp integration
- [x] - Repository folder structure
- [x] - Zip file location moved from root

### Release Management
- [x] - Release tagging scripts (create-release-tag.sh/.ps1)
- [x] - Tag v1.0.14: CI workflow fixes and TypeScript error resolution
