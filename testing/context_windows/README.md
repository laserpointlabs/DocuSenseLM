# Context Window Performance Testing

This directory contains all work related to context window performance testing and analysis.

## Contents

### Test Scripts
- `test_context_window_performance.py` - Main test script that runs performance tests across different models, context windows, and corpus sizes
- `analyze_results.py` - Analysis script that generates plots and statistics from test results

### Documentation
- `CONTEXT_WINDOW_STUDY.md` - Comprehensive study document with findings and recommendations

### Results
- `results/` - Contains all test results, analysis outputs, and visualizations
  - `results_*.csv` - Raw test data in CSV format
  - `results_*.json` - Raw test data in JSON format
  - `analysis/*.png` - Visualization plots
  - `analysis/*_report.txt` - Statistical analysis reports

## Running Tests

```bash
# Run the performance test
python3 test_context_window_performance.py

# Analyze results and generate plots
python3 analyze_results.py
```

## Test Configuration

- **Models**: llama3.2:1b, llama3.2:3b
- **Context Windows**: 2048, 4096, 8192, 16384 tokens
- **Corpus Sizes**: 25%, 50%, 75%, 90% of each context window
- **Questions**: 3 different question types per configuration

## Key Findings

See `CONTEXT_WINDOW_STUDY.md` for detailed findings. Summary:
- 4096 tokens is the optimal context window size
- llama3.2:1b is faster (1.18s avg) but lower confidence
- llama3.2:3b has higher confidence (59.05) but slower (1.64s avg)


