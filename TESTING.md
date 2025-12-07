# Testing Guide for NDA Tool Lite

This guide covers how to run both manual and automated tests for the NDA Tool Lite application.

## Prerequisites

- Node.js and npm
- Python 3.12+
- `venv` setup and dependencies installed (see `README.md` or `BUILDing.md`)

## Automated E2E Tests

We have created an automated end-to-end test suite that verifies the core API functionality (which drives the frontend).

### Setup

1. Activate the Python virtual environment:
   ```bash
   source python/venv/bin/activate
   ```

2. Install test dependencies:
   ```bash
   pip install pytest requests
   ```

### Running the Tests

1. Start the backend server in one terminal:
   ```bash
   # Use port 14242 as expected by the tests
   source python/venv/bin/activate
   export PORT=14242
   python python/server.py
   ```

2. Run the tests in another terminal:
   ```bash
   source python/venv/bin/activate
   python -m pytest tests/test_lite_e2e.py
   ```

### What is Tested

The `tests/test_lite_e2e.py` script covers:
- Backend Health Check
- Configuration loading
- Document Upload (NDA type)
- Document Processing (RAG indexing)
- Chat functionality (RAG retrieval)
- Status Report Generation (LLM integration)
- Document Reprocessing
- Document Deletion

## Manual UI Testing

To test the User Interface manually:

1. Start the backend (as above).
2. Start the frontend:
   ```bash
   npm run dev
   ```
3. Open `http://localhost:5173` in your browser.

### Test Scenarios

1. **Dashboard Load**: Verify the dashboard shows "System Ready" and correct counts.
2. **Upload**: Go to "Documents", upload a PDF/DOCX. Verify it appears in the list.
3. **Processing**: Wait for status to change from "pending" to "processed".
4. **Preview**: Click "View" (Eye icon) to see the PDF preview and extracted metadata.
5. **Chat**: Go to "Chat & Ask", ask a question about the document (e.g., "What is the expiration date?").
6. **Reprocess**: In "Documents", click the Refresh icon to re-run indexing/extraction.
7. **Report**: In "Dashboard", click "Generate Status Report" and verify the email draft appears.
8. **Delete**: In "Documents", delete the file and verify it disappears.

