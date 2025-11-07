# RAG Testing Suite

Central location for all RAG-related testing scripts, results, and reports.

## Structure

```
testing/rag/
├── scripts/          # Test scripts
├── results/          # Test result JSON files
├── reports/          # Generated reports (markdown, etc.)
└── README.md         # This file
```

## Test Scripts

### 1. `comprehensive_rag_test.py`
**Purpose**: Aggressive comprehensive testing of all RAG capabilities

**Tests**:
- Company name flexibility (full, partial, misspelled)
- Misspelling tolerance
- Query phrasing variations
- Synonym recognition
- Structured metadata questions
- Location questions
- Error handling

**Usage**:
```bash
docker exec nda-api python3 /app/testing/rag/scripts/comprehensive_rag_test.py
```

**Output**: Saves JSON results to `results/comprehensive_rag_test_YYYYMMDD_HHMMSS.json`

### 2. `rag_test_suite.py`
**Purpose**: Original RAG test suite with LLM-based evaluation

**Usage**:
```bash
docker exec nda-api python3 /app/testing/rag/scripts/rag_test_suite.py
```

### 3. `test_query_flexibility.py`
**Purpose**: Tests query flexibility (variations, misspellings, alternate phrasings)

**Usage**:
```bash
docker exec nda-api python3 /app/testing/rag/scripts/test_query_flexibility.py
```

## Running Tests

All tests should be run from within the Docker container:

```bash
# Run comprehensive test
docker exec nda-api python3 /app/testing/rag/scripts/comprehensive_rag_test.py

# Run flexibility test
docker exec nda-api python3 /app/testing/rag/scripts/test_query_flexibility.py

# Run original test suite
docker exec nda-api python3 /app/testing/rag/scripts/rag_test_suite.py
```

## Results

Test results are saved as JSON files in `results/` with timestamps:
- `comprehensive_rag_test_YYYYMMDD_HHMMSS.json`
- `flexibility_test_YYYYMMDD_HHMMSS.json`
- `rag_test_results_YYYYMMDD_HHMMSS.json`

## Reports

Generated reports (markdown, graphs, etc.) should be saved in `reports/`.

## Test Criteria

### Pass Criteria
- Answer contains expected terms/keywords
- Confidence meets minimum threshold
- Answer is not "cannot find" (unless expected)
- No errors during execution

### Aggressive Validation
The comprehensive test suite uses strict validation:
- Minimum confidence thresholds per test
- Expected term matching
- Error handling validation
- Multiple query variations

## Adding New Tests

1. Add test cases to `comprehensive_rag_test.py` in the `TEST_CASES` list
2. Follow the structure:
   ```python
   {
       "question": "Test question",
       "expected_contains": ["term1", "term2"],
       "min_confidence": 0.8,
       "description": "What this test validates"
   }
   ```
3. Run the test and verify results
4. Update this README if adding new test categories

