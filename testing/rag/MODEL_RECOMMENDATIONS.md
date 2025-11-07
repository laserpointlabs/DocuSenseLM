# Recommended Ollama Models for RAG (in order of recommendation)

## Current Model
- llama3.2:3b (small, fast, but limited reasoning)

## Recommended Upgrades

### 1. Mistral 7B (RECOMMENDED STARTING POINT)
```bash
ollama pull mistral:7b
```
- **Size**: ~4.1GB
- **Context**: 8k tokens (can be extended)
- **Best for**: Balanced performance and speed
- **Why**: Excellent instruction following, good reasoning, faster than larger models
- **Set in .env**: `OLLAMA_MODEL=mistral:7b`

### 2. Llama 3.1 8B
```bash
ollama pull llama3.1:8b
```
- **Size**: ~4.7GB
- **Context**: 128k tokens (huge!)
- **Best for**: Long context RAG, complex reasoning
- **Why**: Meta's latest, excellent reasoning, massive context window
- **Set in .env**: `OLLAMA_MODEL=llama3.1:8b`

### 3. Mixtral 8x7B (BEST QUALITY)
```bash
ollama pull mixtral:8x7b
```
- **Size**: ~26GB
- **Context**: 32k tokens
- **Best for**: Maximum accuracy, complex queries
- **Why**: Mixture of experts, outperforms GPT-3.5, best quality
- **Set in .env**: `OLLAMA_MODEL=mixtral:8x7b`
- **Note**: Requires significant GPU memory (24GB+ VRAM)

### 4. Qwen2.5 7B
```bash
ollama pull qwen2.5:7b
```
- **Size**: ~4.4GB
- **Context**: 32k tokens
- **Best for**: RAG tasks, multilingual support
- **Why**: Strong RAG performance, good instruction following
- **Set in .env**: `OLLAMA_MODEL=qwen2.5:7b`

### 5. Llama 3.2 11B
```bash
ollama pull llama3.2:11b
```
- **Size**: ~6.1GB
- **Context**: 128k tokens
- **Best for**: Larger Llama option with huge context
- **Why**: More parameters than 3.2:3b, better reasoning
- **Set in .env**: `OLLAMA_MODEL=llama3.2:11b`

## Quick Setup for Mistral 7B

1. Pull the model:
```bash
docker exec nda-ollama ollama pull mistral:7b
```

2. Update your .env file:
```bash
OLLAMA_MODEL=mistral:7b
```

3. Restart the API service:
```bash
docker-compose restart api
```

4. Test with:
```bash
docker exec nda-api python3 /app/testing/rag/scripts/comprehensive_rag_test.py
```

## Performance Expectations

| Model | Expected Accuracy | Speed | VRAM Needed |
|-------|------------------|-------|-------------|
| llama3.2:3b (current) | 84% | Fast | ~4GB |
| mistral:7b | 88-92% | Medium | ~6GB |
| llama3.1:8b | 90-93% | Medium | ~8GB |
| mixtral:8x7b | 93-96% | Slower | ~24GB |
| qwen2.5:7b | 89-92% | Medium | ~6GB |

## Recommendation

Start with **Mistral 7B** - it's a great balance and should improve your accuracy from 84% to ~90%+. If you have GPU memory available, try **Llama 3.1 8B** for even better results with the huge context window.

