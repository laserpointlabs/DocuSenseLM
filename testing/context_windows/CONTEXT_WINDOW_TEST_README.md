# Context Window Performance Test

This test compares different context window sizes to measure their impact on:
- **Response Time**: How long it takes to generate an answer
- **Memory Usage**: GPU memory consumed
- **Response Quality**: Consistency of answers across multiple runs

## How It Works

The test script (`test_context_window_performance.sh`):
1. Tests multiple context sizes: 4096, 8192, 16384, 32000
2. For each size:
   - Updates `OLLAMA_CONTEXT_LENGTH` in docker-compose.yml
   - Restarts the Ollama container
   - Runs the same question 3 times
   - Measures response time and GPU memory usage
   - Captures responses for comparison
3. Generates a summary comparing all results

## Running the Test

```bash
./test_context_window_performance.sh
```

**Requirements:**
- Ollama container must be running
- Model `llama3.2:1b` must be available (will be pulled automatically)
- `bc` calculator (usually pre-installed)

**Duration:** ~10-15 minutes (depends on model loading times)

## Test Question

The default test question is: "What is the effective date of the NDA?"

You can modify this in the script by changing the `TEST_QUESTION` variable.

## Results

Results are saved to `./context_test_results/`:
- Individual test results: `context_<size>_test<num>.txt`
- Summary: `summary_<timestamp>.txt`

## What to Look For

1. **Response Time**: Larger context windows may be slightly slower due to:
   - More memory allocation
   - Larger KV cache
   - More computation per token

2. **Memory Usage**: Larger context = more GPU memory:
   - Context size directly affects KV cache size
   - Formula: ~Memory = Model Size + (Context Size × 2 × Hidden Size × Bytes per param)

3. **Response Consistency**: All runs should produce similar answers
   - If answers vary significantly, the model might be unstable
   - This could indicate the context size is too large for the model

## Expected Results

For a small model like `llama3.2:1b`:
- **4096**: Fastest, lowest memory, good for simple queries
- **8192**: Slightly slower, more memory, better for longer context
- **16384**: Moderate speed, higher memory, good balance
- **32000**: Slowest, highest memory, best for very long documents

**Note**: The model's maximum effective context may be limited by its training. Check logs for warnings like:
```
n_ctx_per_seq (32000) < n_ctx_train (131072)
```

## Customizing the Test

Edit the script to:
- Change context sizes: `CONTEXT_SIZES=(4096 8192 16384 32000)`
- Change test question: `TEST_QUESTION="Your question here"`
- Change number of runs: Modify the loop `for test_num in 1 2 3`
- Change model: Replace `llama3.2:1b` with your model

