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
1.  Start MCP OCR server (port 7001).
2.  Start MCP RAG server (port 7002).
3.  Start the backend server (if not running, port 14242).
4.  Run `tests/test_mcp_integration.py` (MCP Server Health Tests).
5.  Run `tests/test_backend_mcp_integration.py` (Backend MCP Integration Tests).
6.  Run `tests/test_classify.py` and `tests/test_real_pdf_classification.py` (Classification Tests).
7.  Run `tests/test_lite_e2e.py` (Functional API Tests).
8.  Run `tests/test_llm_efficacy.py` (LLM Accuracy Tests).
9.  Clean up all server processes.

### Test Descriptions

*   **MCP Server Integration Tests (`tests/test_mcp_integration.py`)**:
    *   Verifies that both MCP OCR and RAG servers start correctly.
    *   Tests server health endpoints and basic connectivity.
    *   Ensures servers are ready for use by the backend.

*   **Backend MCP Integration Tests (`tests/test_backend_mcp_integration.py`)**:
    *   Verifies backend uses MCP OCR server for document text extraction.
    *   Verifies backend uses MCP RAG server for document indexing.
    *   Tests complete upload -> classify -> extract -> index workflow.
    *   Ensures no fallback code paths are used.

*   **Classification Tests (`tests/test_classify.py`, `tests/test_real_pdf_classification.py`)**:
    *   Tests document type classification using MCP OCR + LLM.
    *   Verifies classification works with real PDFs from data folder.
    *   CI-safe tests with mocked LLM responses.

*   **Functional E2E Tests (`tests/test_lite_e2e.py`)**:
    *   Verifies API health, configuration, file upload/delete, and basic processing flows.
    *   Ensures the application mechanics work correctly.

*   **LLM Efficacy Tests (`tests/test_llm_efficacy.py`)**:
    *   **Competency Extraction**: Verifies correct extraction of expiration dates and parties.
    *   **RAG Retrieval**: Ensures the correct document is cited for relevant queries.
    *   **Response Quality**: Checks if the LLM answers specific questions correctly (e.g., termination terms).
    *   **Hallucination Check**: Verifies the LLM refuses to answer questions about non-existent information.
    *   **Report Generation**: Checks structure and content inclusion in generated reports.

## MCP Server Tests

The MCP (Microservice Communication Protocol) servers are automatically started by the CI script. To run MCP tests manually:

```bash
# Start MCP servers (in separate terminals)
export MCP_OCR_PORT=7001
python -m mcp_ocr_server.main

export MCP_RAG_PORT=7002
export OPENAI_API_KEY=your_key_here
python -m mcp_rag_server.main

# Run MCP tests
export MCP_OCR_URL=http://localhost:7001
export MCP_RAG_URL=http://localhost:7002
python -m pytest tests/test_mcp_integration.py tests/test_backend_mcp_integration.py -v
```

## Classification & OCR Tests

- CI-safe classifier test (stubbed LLM; no network):
  ```bash
  python -m pytest tests/test_classify.py
  ```
- Real PDF classification test (requires MCP servers):
  ```bash
  export MCP_OCR_URL=http://localhost:7001
  export MCP_RAG_URL=http://localhost:7002
  python -m pytest tests/test_real_pdf_classification.py -v
  ```
- OCR dependencies for scanned PDFs: `easyocr` and `Pillow` must be installed:
  ```bash
  pip install easyocr Pillow
  ```

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
