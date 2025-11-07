#!/bin/bash

# Test script to monitor GPU utilization during Ollama inference
# Helps diagnose why GPU utilization is low despite model being on GPU

echo "=== GPU Utilization Test ==="
echo ""

# Check if Ollama is running
if ! docker ps | grep -q nda-ollama; then
    echo "❌ Ollama container is not running"
    exit 1
fi

echo "1. Current GPU status:"
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv
echo ""

echo "2. Current model status:"
docker exec nda-ollama ollama ps
echo ""

echo "3. Testing with llama3.2:1b (small model)..."
echo "   Starting inference and monitoring GPU every 0.5 seconds..."
echo ""

# Start monitoring in background
(
    for i in {1..20}; do
        nvidia-smi --query-gpu=index,utilization.gpu,utilization.memory,memory.used --format=csv,noheader
        sleep 0.5
    done
) > /tmp/gpu_monitor.txt &
MONITOR_PID=$!

# Run inference
docker exec nda-ollama ollama run llama3.2:1b "Write a comprehensive technical explanation of how large language models work, including transformer architecture, attention mechanisms, tokenization, and training processes. Make it detailed and educational." > /dev/null 2>&1

# Stop monitoring
kill $MONITOR_PID 2>/dev/null || true
wait $MONITOR_PID 2>/dev/null || true

echo "GPU utilization during inference:"
cat /tmp/gpu_monitor.txt | head -20
echo ""

MAX_UTIL=$(cat /tmp/gpu_monitor.txt | cut -d',' -f2 | sed 's/ %//' | sort -n | tail -1)
echo "Maximum GPU utilization observed: ${MAX_UTIL}%"
echo ""

if [ "${MAX_UTIL:-0}" -lt 10 ]; then
    echo "⚠️  Low GPU utilization detected!"
    echo ""
    echo "Possible reasons:"
    echo "1. Model is too small (1B parameters) - inference is very fast"
    echo "2. High context window (32000) may cause CPU overhead"
    echo "3. Pipeline parallelism may be using CPU"
    echo ""
    echo "Recommendations:"
    echo "- Test with a larger model (llama3.2:3b or 8b)"
    echo "- Try reducing context size temporarily"
    echo "- Check if OLLAMA_NUM_PARALLEL=1 is set (should reduce CPU usage)"
    echo ""
    echo "Current settings:"
    docker exec nda-ollama env | grep OLLAMA
else
    echo "✅ GPU utilization is good (${MAX_UTIL}%)"
fi

rm -f /tmp/gpu_monitor.txt

