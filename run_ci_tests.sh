#!/bin/bash
set -e

cleanup() {
    if [ ! -z "$SERVER_PID" ]; then
        echo "CLEANUP: Stopping backend server (PID $SERVER_PID)..."
        kill $SERVER_PID 2>/dev/null || true
    fi
    if [ ! -z "$OCR_PID" ]; then
        echo "CLEANUP: Stopping MCP OCR server (PID $OCR_PID)..."
        kill $OCR_PID 2>/dev/null || true
    fi
    if [ ! -z "$RAG_PID" ]; then
        echo "CLEANUP: Stopping MCP RAG server (PID $RAG_PID)..."
        kill $RAG_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

echo "========================================"
echo "    DocuSenseLM - CI Test Runner       "
echo "========================================"

# 1. Environment Setup
echo "SETUP: Activating virtual environment..."
source python/venv/bin/activate

# 2. Start MCP OCR Server
echo "SETUP: Starting MCP OCR server..."
export MCP_OCR_PORT=7001
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/python"
python -m mcp_ocr_server.main > mcp_ocr.log 2>&1 &
OCR_PID=$!
echo "MCP OCR server started with PID $OCR_PID. Waiting for health check..."

# Wait for OCR server
for i in {1..30}; do
    if curl -s http://localhost:7001/ocr_page > /dev/null 2>&1; then
        echo "✅ MCP OCR server is ready!"
        break
    fi
    sleep 1
done

# 3. Start MCP RAG Server
echo "SETUP: Starting MCP RAG server..."
export MCP_RAG_PORT=7002
if [ -z "$OPENAI_API_KEY" ]; then
    echo "WARNING: OPENAI_API_KEY not set. RAG server may fail."
fi
python -m mcp_rag_server.main > mcp_rag.log 2>&1 &
RAG_PID=$!
echo "MCP RAG server started with PID $RAG_PID. Waiting for health check..."

# Wait for RAG server
for i in {1..30}; do
    if curl -s http://localhost:7002/query > /dev/null 2>&1; then
        echo "✅ MCP RAG server is ready!"
        break
    fi
    sleep 1
done

# 4. Check/Start Backend
echo "SETUP: Checking backend server..."
if curl -s http://localhost:14242/health > /dev/null; then
    echo "Backend already running on port 14242."
else
    echo "Backend not running. Starting..."
    export PORT=14242
    export MCP_OCR_URL=http://localhost:7001
    export MCP_RAG_URL=http://localhost:7002
    python python/server.py > server.log 2>&1 &
    SERVER_PID=$!
    echo "Backend started with PID $SERVER_PID. Waiting for health check..."
    
    # Wait for health
    for i in {1..30}; do
        if curl -s http://localhost:14242/health > /dev/null; then
            echo "✅ Backend is healthy!"
            break
        fi
        sleep 1
    done
fi

# 5. Run MCP Server Integration Tests
echo "----------------------------------------"
echo "TEST: Running MCP Server Integration Tests..."
python -m pytest tests/test_mcp_integration.py -v
echo "✅ MCP server integration tests passed."

# 6. Run MCP Backend Integration Tests
echo "----------------------------------------"
echo "TEST: Running Backend MCP Integration Tests..."
export MCP_OCR_URL=http://localhost:7001
export MCP_RAG_URL=http://localhost:7002
python -m pytest tests/test_backend_mcp_integration.py -v
echo "✅ Backend MCP integration tests passed."

# 7. Run Classification Tests
echo "----------------------------------------"
echo "TEST: Running Document Classification Tests..."
python -m pytest tests/test_classify.py tests/test_real_pdf_classification.py -v
echo "✅ Classification tests passed."

# 8. Run Functional E2E Tests
echo "----------------------------------------"
echo "TEST: Running Functional E2E Tests..."
python -m pytest tests/test_lite_e2e.py -v
echo "✅ Functional tests passed."

# 9. Run LLM Efficacy Tests
echo "----------------------------------------"
echo "TEST: Running LLM Efficacy/Quality Tests..."
python -m pytest tests/test_llm_efficacy.py -v
echo "✅ LLM efficacy tests passed."

echo "========================================"
echo "    ALL TESTS PASSED SUCCESSFULLY       "
echo "========================================"
