# Testing Guide for NDA Tool Lite

This guide covers how to run both manual and automated tests for the NDA Tool Lite application.

## Prerequisites

- Node.js and npm
- Python 3.12+
- `venv` setup and dependencies installed (see `README.md` or `BUILDing.md`)

## Automated CI Test Suite

We have a comprehensive CI script that runs both functional end-to-end tests and LLM efficacy tests.

### Running All Tests

Simply run the CI runner script:

```bash
chmod +x run_ci_tests.sh
./run_ci_tests.sh
```

This script will:
1.  Start the backend server (if not running).
2.  Run `tests/test_lite_e2e.py` (Functional API Tests).
3.  Run `tests/test_llm_efficacy.py` (LLM Accuracy Tests).
4.  Clean up the server process.

### Test Descriptions

*   **Functional E2E Tests (`tests/test_lite_e2e.py`)**:
    *   Verifies API health, configuration, file upload/delete, and basic processing flows.
    *   Ensures the application mechanics work correctly.

*   **LLM Efficacy Tests (`tests/test_llm_efficacy.py`)**:
    *   **Competency Extraction**: Verifies correct extraction of expiration dates and parties.
    *   **RAG Retrieval**: Ensures the correct document is cited for relevant queries.
    *   **Response Quality**: Checks if the LLM answers specific questions correctly (e.g., termination terms).
    *   **Hallucination Check**: Verifies the LLM refuses to answer questions about non-existent information.
    *   **Report Generation**: Checks structure and content inclusion in generated reports.

## Manual UI Testing

To test the User Interface manually:

1. Start the backend:
   ```bash
   source python/venv/bin/activate
   export PORT=14242
   python python/server.py
   ```
2. Start the frontend:
   ```bash
   npm run dev
   ```
3. Open `http://localhost:5173`.

### Key Scenarios

1. **Dashboard Load**: Verify "System Ready".
2. **Upload**: Upload `green_nda.pdf`.
3. **Processing**: Wait for "processed" status.
4. **Chat**: Ask "What is the termination clause?".
5. **Report**: Click "Generate Status Report".
