# Context Window Performance Study

## Executive Summary

This study analyzes the performance of two Llama models (1B and 3B parameters) across varying context window sizes and corpus sizes. The analysis reveals key trade-offs between response time, confidence, and context window configuration.

## Methodology

- **Models Tested**: llama3.2:1b, llama3.2:3b
- **Context Window Sizes**: 2048, 4096, 8192, 16384 tokens
- **Corpus Sizes**: 25%, 50%, 75%, and 90% of each context window
- **Test Questions**: 3 different question types per configuration
- **Runs per Configuration**: 3 runs (averaged)
- **Total Tests**: 96 configurations

## Key Findings

### 1. Model Performance Comparison

**llama3.2:1b (1B parameters)**
- Average response time: **1.18 seconds**
- Average confidence: **54.69**
- Speed advantage: ~28% faster than 3B model
- Best for: Quick responses, lower resource usage

**llama3.2:3b (3B parameters)**
- Average response time: **1.64 seconds**
- Average confidence: **59.05**
- Quality advantage: ~8% higher confidence
- Best for: Higher quality responses, more complex queries

### 2. Context Window Size Impact

| Context Size | Avg Response Time | Avg Confidence |
|-------------|-------------------|----------------|
| 2048        | 1.24s            | 54.19         |
| 4096        | 1.42s            | 60.24         |
| 8192        | 1.42s            | 55.80         |
| 16384       | 1.56s            | 57.26         |

**Observations:**
- **4096 tokens** provides the best balance: highest confidence (60.24) with reasonable speed
- Response time increases modestly with larger context windows (~25% from 2048 to 16384)
- Confidence peaks at 4096, then slightly decreases for larger windows
- Larger context windows don't always improve confidence, suggesting diminishing returns

### 3. Corpus Size Impact

- **Smaller corpus (25-50% of context)**: Faster responses, lower confidence
- **Medium corpus (75% of context)**: Good balance
- **Large corpus (90% of context)**: Slightly slower, variable confidence

### 4. Optimal Configurations

**Fastest Configuration:**
- Model: llama3.2:1b
- Context: 4096 tokens
- Corpus: 9216 characters (~2304 tokens)
- Response Time: **0.46 seconds**

**Highest Confidence:**
- Model: llama3.2:3b
- Context: 16384 tokens
- Corpus: 12288 characters (~3072 tokens)
- Confidence: **100.00**

## Recommendations

### For Speed-Critical Applications
- Use **llama3.2:1b** with **4096 token context window**
- Keep corpus size at 50-75% of context window
- Expected response time: ~1.0-1.2 seconds

### For Quality-Critical Applications
- Use **llama3.2:3b** with **4096-8192 token context window**
- Use 75-90% of context window for corpus
- Expected response time: ~1.5-2.0 seconds
- Expected confidence: 55-60

### For Balanced Applications
- Use **llama3.2:3b** with **4096 token context window**
- Use 75% of context window for corpus
- Provides good balance of speed and quality

## Performance Insights

1. **Diminishing Returns**: Context windows larger than 4096 tokens show minimal confidence improvements but increase response time.

2. **Model Size Trade-off**: The 3B model provides ~8% better confidence but is ~28% slower than the 1B model.

3. **Corpus Utilization**: Using 75-90% of the context window generally provides optimal results, with 90% sometimes showing slight performance degradation.

4. **Response Time Stability**: Response times are relatively stable across configurations, with most queries completing in 1-2 seconds.

## Visualizations

The following plots are available in `tests/results/analysis/`:

1. **response_time_vs_corpus.png**: Shows how response time varies with corpus size for each model
2. **response_time_vs_context.png**: Compares average response time across context window sizes
3. **confidence_vs_context.png**: Shows confidence scores across different context windows
4. **response_time_heatmap.png**: Heatmap visualization of response times by context and corpus size
5. **model_comparison.png**: Side-by-side comparison of both models across multiple dimensions

## Conclusion

The study demonstrates that:
- **4096 tokens** is the optimal context window size for most use cases
- **llama3.2:1b** is best for speed-critical applications
- **llama3.2:3b** is best for quality-critical applications
- Larger context windows (>8192) provide minimal benefits for the added latency
- Corpus size should be 75-90% of the context window for optimal performance

## Data Files

- Raw data: `tests/results/results_20251106_072936.csv`
- Analysis report: `tests/results/analysis/results_20251106_072936_report.txt`
- Visualizations: `tests/results/analysis/*.png`

