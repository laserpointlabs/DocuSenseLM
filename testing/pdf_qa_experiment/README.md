# PDF Q&A Experiment

This experiment tests the LLM's ability to answer questions about a full PDF document using a 16k context window.

## Setup

- **PDF**: Fanuc America Corporation NDA (3 pages, ~1,897 tokens)
- **Model**: llama3.2:3b
- **Context Window**: 16384 tokens
- **Approach**: Send entire PDF text to LLM with questions

## Files

- `fanuc_nda.pdf` - The test PDF document
- `extract_pdf.py` - Extracts text from PDF and creates expected data template
- `expected_data.json` - Expected answers based on ontology structure
- `qa_evaluation.py` - Runs Q&A evaluation and measures accuracy
- `extracted_text.txt` - Full extracted text from PDF
- `results/` - Evaluation results (JSON and CSV)

## Results Summary

**Latest Run:**
- **Accuracy**: 9/10 questions correct (90.0%)
- **Average Match Score**: 0.85
- **Average Response Time**: 0.75 seconds
- **Average Confidence**: 16.6

### Question Performance

| Question | Category | Correct | Score | Notes |
|----------|----------|---------|-------|-------|
| Effective date | metadata | ✅ | 0.80 | Found year 2025 |
| Expiration date | metadata | ✅ | 0.80 | Found year 2028 |
| Parties | parties | ✅ | 1.00 | Found both parties |
| Mutual status | metadata | ✅ | 1.00 | Correctly identified |
| Term (months) | term | ✅ | 1.00 | Converted 3 years to 36 months |
| Governing law | metadata | ✅ | 1.00 | Found California |
| Fanuc address | parties | ✅ | 0.90 | Normalized match |
| Kidde address | parties | ✅ | 1.00 | Exact match |
| Confidentiality period | term | ✅ | 1.00 | Converted years to months |
| Expiration date (when) | metadata | ❌ | 0.00 | Found term but not exact date |

## Key Findings

1. **Full PDF chat works well** - 90% accuracy with 16k context window
2. **Fast responses** - Average 0.75 seconds per question
3. **Good at extracting structured data** - Parties, dates, terms all correctly identified
4. **Flexible answer formats** - Handles "3 years" vs "36 months" correctly
5. **Date precision** - Sometimes finds year but not exact date

## Expected Data Structure

Based on ontology, the expected data includes:
- **parties**: Name, address, type (disclosing/receiving)
- **effective_date**: ISO format YYYY-MM-DD
- **expiration_date**: ISO format YYYY-MM-DD
- **term_months**: Integer
- **governing_law**: String
- **is_mutual**: Boolean
- **nda_type**: "mutual" or "unilateral"

## Running the Experiment

```bash
# 1. Extract PDF text and create expected data
python3 extract_pdf.py

# 2. Review and update expected_data.json with actual values

# 3. Run Q&A evaluation
python3 qa_evaluation.py
```

## Evaluation Metrics

- **Correct**: Boolean - whether answer matches expected
- **Match Score**: 0.0-1.0 - how well answer matches expected
- **Confidence**: 0-100 - based on answer length/completeness
- **Duration**: Response time in seconds

