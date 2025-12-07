#!/bin/bash
set -e

cleanup() {
    if [ ! -z "$SERVER_PID" ]; then
        echo "CLEANUP: Stopping backend server (PID $SERVER_PID)..."
        kill $SERVER_PID
    fi
}
trap cleanup EXIT

echo "========================================"
echo "    NDA Tool Lite - CI Test Runner      "
echo "========================================"

# 1. Environment Setup
echo "SETUP: Activating virtual environment..."
source python/venv/bin/activate

# 2. Check/Start Backend
echo "SETUP: Checking backend server..."
if curl -s http://localhost:14242/health > /dev/null; then
    echo "Backend already running on port 14242."
else
    echo "Backend not running. Starting..."
    export PORT=14242
    python python/server.py > server.log 2>&1 &
    SERVER_PID=$!
    echo "Backend started with PID $SERVER_PID. Waiting for health check..."
    
    # Wait for health
    for i in {1..30}; do
        if curl -s http://localhost:14242/health > /dev/null; then
            echo "Backend is healthy!"
            break
        fi
        sleep 1
    done
fi

# 3. Run Functional E2E Tests
echo "----------------------------------------"
echo "TEST: Running Functional E2E Tests..."
python -m pytest tests/test_lite_e2e.py -v
echo "✅ Functional tests passed."

# 4. Run LLM Efficacy Tests
echo "----------------------------------------"
echo "TEST: Running LLM Efficacy/Quality Tests..."
python -m pytest tests/test_llm_efficacy.py -v
echo "✅ LLM efficacy tests passed."

echo "========================================"
echo "    ALL TESTS PASSED SUCCESSFULLY       "
echo "========================================"
