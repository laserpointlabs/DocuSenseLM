#!/bin/bash

# Test script to compare different context window sizes
# Measures: response time, response quality, and GPU memory usage

set -e

TEST_QUESTION="What is the effective date of the NDA?"
CONTEXT_SIZES=(4096 8192 16384 32000)
RESULTS_DIR="$(dirname "$0")/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=== Context Window Performance Test ==="
echo ""
echo "Test Question: $TEST_QUESTION"
echo "Context Sizes to Test: ${CONTEXT_SIZES[@]}"
echo "Results will be saved to: $RESULTS_DIR"
echo ""

# Create results directory
mkdir -p "$RESULTS_DIR"

# Check if Ollama container is running
if ! docker ps | grep -q nda-ollama; then
    echo "❌ Ollama container is not running"
    echo "Start it with: docker compose up -d ollama"
    exit 1
fi

# Function to update context length and restart container
update_context_length() {
    local context_size=$1
    echo -e "${YELLOW}Setting context length to $context_size...${NC}"
    
    # Update docker-compose.yml
    cd /home/jdehart/Working/ndaTool
    
    # Check if OLLAMA_CONTEXT_LENGTH already exists
    if grep -q "OLLAMA_CONTEXT_LENGTH" docker-compose.yml; then
        # Replace existing value
        sed -i "s/OLLAMA_CONTEXT_LENGTH=[0-9]*/OLLAMA_CONTEXT_LENGTH=$context_size/" docker-compose.yml
    else
        # Add after OLLAMA_USE_GPU
        sed -i "/OLLAMA_USE_GPU=1/a\      - OLLAMA_CONTEXT_LENGTH=$context_size" docker-compose.yml
    fi
    
    # Recreate container to apply new env var
    docker compose up -d --force-recreate ollama > /dev/null 2>&1
    
    # Wait for container to be ready
    echo "   Waiting for Ollama to be ready..."
    for i in {1..30}; do
        if docker exec nda-ollama curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    # Verify environment variable is set
    ACTUAL_SIZE=$(docker exec nda-ollama env | grep OLLAMA_CONTEXT_LENGTH | cut -d'=' -f2)
    if [ "$ACTUAL_SIZE" = "$context_size" ]; then
        echo -e "   ${GREEN}✅ Context length set to $context_size${NC}"
    else
        echo -e "   ${RED}❌ Failed to set context length (got: $ACTUAL_SIZE)${NC}"
        return 1
    fi
    
    # Unload any existing models
    docker exec nda-ollama ollama stop llama3.2:1b 2>/dev/null || true
    sleep 2
}

# Function to run a test with timing
run_test() {
    local context_size=$1
    local test_num=$2
    local output_file="$RESULTS_DIR/context_${context_size}_test${test_num}.txt"
    
    echo "   Running test $test_num..."
    
    # Get initial GPU memory
    INITIAL_MEM=$(docker exec nda-ollama nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
    
    # Run the query and measure time
    START_TIME=$(date +%s.%N)
    # Use timeout to prevent hanging, capture both stdout and stderr
    RESPONSE=$(timeout 30 docker exec nda-ollama ollama run llama3.2:1b "$TEST_QUESTION" 2>&1 || echo "ERROR: Query timed out or failed")
    END_TIME=$(date +%s.%N)
    
    # Calculate duration
    DURATION=$(echo "$END_TIME - $START_TIME" | bc)
    
    # Get final GPU memory
    FINAL_MEM=$(docker exec nda-ollama nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
    MEMORY_USED=$((FINAL_MEM - INITIAL_MEM))
    
    # Get model status
    MODEL_STATUS=$(docker exec nda-ollama ollama ps 2>&1 | grep llama3.2:1b || echo "Not loaded")
    
    # Save results
    {
        echo "=== Test Results ==="
        echo "Context Size: $context_size"
        echo "Test Number: $test_num"
        echo "Question: $TEST_QUESTION"
        echo "Response Time: ${DURATION}s"
        echo "Initial GPU Memory: ${INITIAL_MEM} MiB"
        echo "Final GPU Memory: ${FINAL_MEM} MiB"
        echo "Memory Used: ${MEMORY_USED} MiB"
        echo "Model Status: $MODEL_STATUS"
        echo ""
        echo "=== Response ==="
        echo "$RESPONSE"
        echo ""
        echo "=== Ollama Logs (context info) ==="
        docker logs nda-ollama 2>&1 | grep -E "n_ctx_per_seq|context" | tail -3
    } > "$output_file"
    
    # Extract just the answer (remove Ollama's prompt/formatting and control characters)
    ANSWER=$(echo "$RESPONSE" | grep -v "^>>>" | grep -v "^$" | sed 's/\x1b\[[0-9;]*m//g' | tail -1 | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    
    echo "   Response time: ${DURATION}s"
    echo "   Answer: ${ANSWER:0:80}..."
    echo "   GPU Memory used: ${MEMORY_USED} MiB"
    
    # Return metrics
    echo "$DURATION|$MEMORY_USED|$ANSWER"
}

# Main test loop
SUMMARY_FILE="$RESULTS_DIR/summary_${TIMESTAMP}.txt"
{
    echo "=== Context Window Performance Test Summary ==="
    echo "Test Question: $TEST_QUESTION"
    echo "Timestamp: $(date)"
    echo ""
    echo "Context Size | Avg Time (s) | Memory (MiB) | Response Quality"
    echo "-------------|--------------|-------------|------------------"
} > "$SUMMARY_FILE"

for context_size in "${CONTEXT_SIZES[@]}"; do
    echo ""
    echo -e "${GREEN}=== Testing Context Size: $context_size ===${NC}"
    
    # Update context length
    update_context_length "$context_size"
    
    # Run 3 tests for averaging
    TIMES=()
    MEMORIES=()
    ANSWERS=()
    
    for test_num in 1 2 3; do
        RESULT=$(run_test "$context_size" "$test_num")
        TIME=$(echo "$RESULT" | cut -d'|' -f1)
        MEM=$(echo "$RESULT" | cut -d'|' -f2)
        ANSWER=$(echo "$RESULT" | cut -d'|' -f3)
        
        TIMES+=("$TIME")
        MEMORIES+=("$MEM")
        ANSWERS+=("$ANSWER")
        
        # Wait between tests
        sleep 2
    done
    
    # Calculate averages
    AVG_TIME=$(printf '%s\n' "${TIMES[@]}" | awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}')
    AVG_MEM=$(printf '%s\n' "${MEMORIES[@]}" | awk '{sum+=$1; count++} END {if(count>0) print int(sum/count); else print 0}')
    
    # Check response consistency (simple check - all answers should be similar)
    UNIQUE_ANSWERS=$(printf '%s\n' "${ANSWERS[@]}" | sort -u | wc -l)
    if [ "$UNIQUE_ANSWERS" -eq 1 ]; then
        CONSISTENCY="Consistent"
    else
        CONSISTENCY="Varied"
    fi
    
    # Add to summary
    printf "%-12s | %-12.3f | %-11s | %s\n" "$context_size" "$AVG_TIME" "$AVG_MEM" "$CONSISTENCY" >> "$SUMMARY_FILE"
    
    echo ""
    echo "   Average Response Time: ${AVG_TIME}s"
    echo "   Average Memory Used: ${AVG_MEM} MiB"
    echo "   Response Consistency: $CONSISTENCY"
done

echo ""
echo -e "${GREEN}=== Test Complete ===${NC}"
echo ""
echo "Results saved to: $RESULTS_DIR"
echo "Summary: $SUMMARY_FILE"
echo ""
cat "$SUMMARY_FILE"

