# CPU Issue Summary

## What We Found

1. **API Response Time**: Fast (0.29-12 seconds depending on prompt length)
2. **CLI Response Time**: ~3 seconds for simple queries
3. **The Real Problem**: The `ollama runner` process uses 30-50% CPU continuously while the model is loaded in memory

## Root Cause

When a model is loaded (with keep-alive), the `ollama runner` process stays running and consumes CPU even when not processing requests. This is likely:
- Pipeline parallelism coordination overhead
- Model state management
- Memory management/polling

## Evidence

- Model loaded: `ollama runner` at 39% CPU continuously
- Model unloaded: `ollama runner` process stops, CPU drops to ~3%

## Solutions

1. **Unload model after use** (if not needed immediately):
   ```bash
   docker exec nda-ollama ollama stop llama3.2:3b
   ```

2. **Reduce keep-alive time** (in docker-compose.yml):
   ```yaml
   - OLLAMA_KEEP_ALIVE=30s  # Instead of default 5 minutes
   ```

3. **Use API instead of CLI** - API doesn't keep model loaded as long

4. **Single GPU only** - Already configured, but pipeline parallelism may still be active

## Current Status

- Response time: ✅ Fast (0.3-12s)
- CPU during inference: ✅ Reasonable (30-55%)
- CPU when idle: ❌ High (30-50% while model loaded)

