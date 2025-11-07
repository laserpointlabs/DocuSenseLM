#!/bin/bash

echo "=== Testing OLLAMA_CONTEXT_LENGTH Environment Variable ==="
echo ""

# Check if Ollama container is running
if ! docker ps | grep -q nda-ollama; then
    echo "❌ Ollama container is not running"
    echo "Start it with: docker compose up -d ollama"
    exit 1
fi

echo "1. Checking environment variable in container..."
CONTEXT_LENGTH=$(docker exec nda-ollama env | grep OLLAMA_CONTEXT_LENGTH | cut -d'=' -f2)
if [ -n "$CONTEXT_LENGTH" ]; then
    echo "   ✅ OLLAMA_CONTEXT_LENGTH is set to: $CONTEXT_LENGTH"
else
    echo "   ⚠️  OLLAMA_CONTEXT_LENGTH is not set (will use model default)"
fi
echo ""

echo "2. Unloading any existing models..."
docker exec nda-ollama ollama ps | grep -v "NAME" | awk '{print $1}' | while read model; do
    if [ -n "$model" ]; then
        echo "   Unloading: $model"
        docker exec nda-ollama ollama stop $model 2>/dev/null || true
    fi
done
sleep 2
echo ""

echo "3. Loading a test model and checking context size..."
echo "   Using llama3.2:1b (small model for quick test)"
docker exec nda-ollama ollama run llama3.2:1b "test" > /dev/null 2>&1 &
sleep 3

echo "4. Checking actual context size used by the model..."
CONTEXT_SIZE=$(docker exec nda-ollama ollama ps | grep llama3.2:1b | awk '{print $5}')
if [ -n "$CONTEXT_SIZE" ]; then
    echo "   Model context size: $CONTEXT_SIZE"
    
    if [ "$CONTEXT_LENGTH" = "32000" ] && [ "$CONTEXT_SIZE" = "32000" ]; then
        echo "   ✅ SUCCESS: Context length matches environment variable!"
    elif [ "$CONTEXT_LENGTH" = "32000" ] && [ "$CONTEXT_SIZE" != "32000" ]; then
        echo "   ⚠️  WARNING: Environment variable is set to 32000 but model shows $CONTEXT_SIZE"
        echo "   This might be because:"
        echo "   - The model's maximum context is smaller than 32000"
        echo "   - The model needs to be reloaded after setting the env var"
        echo "   - Ollama might not support this env var (check Ollama version)"
    elif [ -z "$CONTEXT_LENGTH" ]; then
        echo "   ℹ️  Using model default context size: $CONTEXT_SIZE"
    else
        echo "   ℹ️  Context size: $CONTEXT_SIZE (env var: $CONTEXT_LENGTH)"
    fi
else
    echo "   ❌ Could not determine context size"
fi
echo ""

echo "5. Testing with a larger model (if available)..."
echo "   Note: Larger models may take time to load"
echo "   You can test manually with:"
echo "   docker exec nda-ollama ollama pull llama3.2:3b"
echo "   docker exec nda-ollama ollama run llama3.2:3b 'test'"
echo "   docker exec nda-ollama ollama ps"
echo ""

echo "=== Test Complete ==="
echo ""
echo "To verify the setting took effect:"
echo "1. Check environment: docker exec nda-ollama env | grep OLLAMA_CONTEXT_LENGTH"
echo "2. Load a model: docker exec nda-ollama ollama run llama3.2:1b 'test'"
echo "3. Check context: docker exec nda-ollama ollama ps"

