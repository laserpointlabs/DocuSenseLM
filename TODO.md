# TODO List

## Build & Distribution
- [ ] - Complete cross-platform builds (Linux, Mac, Windows)
- [ ] - Implement deployment and automatic updates
- [ ] - Build GitHub download, new features, and update page
- [ ] - Package dev system in Docker container and host via Cloudflare using containers for both the app and Cloudflare

## Bug Fixes
- [x] - Fix the issue with locking up the text areas after adding a key
- [x] - Fix bulk drag and drop from desktop (Verified working - no changes needed)
- [x] - Extracted data seems like it no longer working (FIXED: Hybrid search + conversation memory)
- [x] - When clearing chat history make sure it's actually removed
- [ ] - Fix PDF viewer white screen issue that is periodic (Note: may just be a rebuild issue)
- [ ] - Chat should not lock when processing in the background

## Performance & Optimization
- [ ] - Review startup logs and investigate/fix slow startup speed
- [x] - Upload all documents first then process in background so the user can walk away (Implemented: `/start-processing` endpoint with parallel processing using ThreadPoolExecutor)

## Features & Enhancements
- [x] - Document type modification after uploading
- [x] - Manual modification of extracted information meta-data for correction
- [x] - Add direct link to local storage
- [x] - Add Show/Hide status to config file to allow user to control display of document type on the dashboard and document collections area
- [ ] - Add a notes key to the extracted data for the user to add notes and dates and other general information. Track date of changes or edits for extracted data and notes.
- [ ] - Should always have access to the extracted meta data for the chat.
- [ ] - Save PDF markups (Nice to have)
- [ ] - Add multi delete capability or delete all - use check marks (Next)

## UI/UX Improvements
- [x] - Show document collections based on document types in config file in documentation page, this should show an explorer like view instead of the current list where users can open/collapse a file view of the document types (simplified to a modal)
- [x] - Improve sort and search on document page
- [x] - Improve how a user sets the document type prior to drag and drop (might naturally be corrected when we improve the collections on the document page)
- [ ] - Improve processing status notifications: fix flaky status when adding/reprocessing documents, add background processing notifications with current status and estimated time to complete, add processing status to dashboard (Next)

## Testing & CI
- [x] - Add CI smoke test (Electron + Playwright) covering startup/health
- [x] - Fix CI test for embeddable Python backend (Windows build workflow)

## Infrastructure & DevOps
- [x] - Get electron-mcp
- [x] - Change Repo Folder
- [x] - Move zip file location out of the root dir
- [ ] - Consider updating the app for better electron MCP automation

## Documentation & Training
- [ ] - Train LLM on how to use this app → add notes to RAG from training folder
- [ ] - Verify chat history length under normal operation

## Release Management
- [x] - Create release tagging scripts (create-release-tag.sh/.ps1)
- [x] - Tag v1.0.14: CI workflow fixes and TypeScript error resolution
- [ ] - Ensure all TODO items get tagged when completed
