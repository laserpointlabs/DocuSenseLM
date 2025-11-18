#!/bin/bash
# Consolidate test files - remove duplicates and organize

cd "$(dirname "$0")/.."

echo "Consolidating test files..."

# Move any results directories to tests/results
mkdir -p tests/results
if [ -d "context_test_results" ]; then
    mv context_test_results/* tests/results/ 2>/dev/null
    rmdir context_test_results 2>/dev/null
fi
if [ -d "context_performance_results" ]; then
    mv context_performance_results/* tests/results/ 2>/dev/null
    rmdir context_performance_results 2>/dev/null
fi
if [ -d "model_context_test_results" ]; then
    mv model_context_test_results/* tests/results/ 2>/dev/null
    rmdir model_context_test_results 2>/dev/null
fi

echo "✅ Results moved to tests/results/"











