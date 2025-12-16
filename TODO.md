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
- [ ] - Consider updating the app for better electron MCP automation
- [ ] - Set up automated release process (GitHub Actions)
- [ ] - Create release checklist template
- [ ] - Document release process and rollback procedures

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
