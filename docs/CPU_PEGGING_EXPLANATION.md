# Why CPU is Pegging

## Root Cause

The CPU is maxing out because of **pipeline parallelism** with `n_copies=4`. This happens when Ollama detects multiple GPUs (you have 4 RTX 4060 Ti GPUs).

### What's Happening:

1. **Pipeline Parallelism**: Ollama automatically enables pipeline parallelism (`n_copies=4`) when it sees 4 GPUs
   - This creates 4 copies of the model for parallel processing
   - Requires heavy CPU coordination between GPU copies
   - Logs show: `llama_context: pipeline parallelism enabled (n_copies=4)`

2. **CPU Threads**: Using 10 CPU threads (`NumThreads:10`) for coordination
   - The `ollama runner` process shows 99.9% CPU usage
   - This is all coordination overhead, not actual inference

3. **CPU-Mapped Memory**: Some model data is mapped to CPU (`CPU_Mapped model buffer size = 308.23 MiB`)
   - This requires CPU-GPU memory transfers
   - Adds to CPU overhead

## Solutions

### Solution 1: Use Single GPU (Recommended)
Limit to one GPU to disable pipeline parallelism:

```yaml
environment:
  - NVIDIA_VISIBLE_DEVICES=0  # Only use first GPU
```

**Pros:**
- Disables pipeline parallelism
- Reduces CPU overhead significantly
- Still uses GPU for inference

**Cons:**
- Only uses 1 of 4 GPUs
- Slightly slower than true multi-GPU (but faster than current CPU-bound state)

### Solution 2: Reduce CPU Threads
Limit CPU threads used for coordination:

```yaml
environment:
  - OLLAMA_NUM_THREAD=4  # Reduce from default 10
```

**Pros:**
- Reduces CPU usage
- Still allows multi-GPU

**Cons:**
- Pipeline parallelism still active
- May still have high CPU usage

### Solution 3: Use Larger Model
Larger models (7B+) better utilize GPU and reduce CPU overhead:

```bash
docker exec nda-ollama ollama pull llama3.2:8b
```

**Pros:**
- Better GPU utilization
- More work on GPU = less CPU coordination

**Cons:**
- Requires more GPU memory
- Slower inference

## Current Configuration

After applying fixes:
- `NVIDIA_VISIBLE_DEVICES=0` - Single GPU only
- `OLLAMA_NUM_THREAD=4` - Reduced CPU threads
- `OLLAMA_CONTEXT_LENGTH=8192` - Reduced context window
- `OLLAMA_NUM_PARALLEL=1` - Single parallel request

## Expected Results

After limiting to single GPU:
- CPU usage should drop significantly (from 99% to ~10-20%)
- GPU utilization should increase (from brief spikes to sustained 50-80%)
- Inference should be faster (less CPU coordination overhead)
- Pipeline parallelism should be disabled (`n_copies=1` in logs)

## Verification

Check if pipeline parallelism is disabled:
```bash
docker logs nda-ollama 2>&1 | grep "pipeline parallelism"
# Should show: n_copies=1 (or not appear at all)
```

Monitor CPU usage:
```bash
docker exec nda-ollama ps aux | grep ollama
# CPU usage should be much lower
```

