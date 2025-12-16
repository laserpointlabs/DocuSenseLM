[ ] - Complet a linux\mac build
[ ] - Windows and mac builds
[x] - Fix the issue with locking up the text areas after adding a key
[x] - Add CI smoke test (Electron + Playwright) covering startup/health
[x] - Fix CI test for embeddable Python backend (Windows build workflow)
[x] - Get electron-mcp
[x] - Change Repo Folder

[ ] - Train llm on how to use this app → add notes to rag from traning folder
[x] - Add direct link to local storage


[x] - Document type modification after uploading
[x] - Manual modification of extracted information meta-data for correction (TODAY)
[x] - Show document colections based on document types in config file in documeation page, this should show an explorer like view instead of the current list where users can open/collaspe a file view of the document types. (simplieifed to a modal)
[x] - Improve sort and search on document page.
[x] - Improve how a user sets the document type prior to drag and drop this might naturally be corrected when we improve the collections on the document page. 

[x] - Fix builk drag and drop from desktop. (Verified working - no changes needed) 
[x] - Add Show/Hide status to config file to all user to control display of document type on the dashboard and document collections area
[ ] - Implement deployment and automatic updates
[ ] - Build github download, new features, and update page
[/] - Improve status of processing when adding new file and when reprocessing document (still a bit flaky)
[x] - Extracted data seems like it no longer working (FIXED: Hybrid search + conversation memory)
[x] - When clearning chat history make sure its actually removed
[ ] - Verify chat history length under normal operation
[ ] - Save pdf markups (Nice to have)
[ ] - add notification of background processing and current status, estimated time to complete, etc. (Next)
[ ] - investigate startup speed its slow 
[ ] - consider updating the app for better electron mcp automation
[ ] - package dev system in docker container and host via cloudflare using containers for both the app and cloudflaire
[ ] - Fix pdf viwers white screen issue that is periodic (Next)

Release Management:
[x] - Create release tagging scripts (create-release-tag.sh/.ps1)
[x] - Tag v1.0.14: CI workflow fixes and TypeScript error resolution
[ ] - Ensure all TODO items get tagged when completed