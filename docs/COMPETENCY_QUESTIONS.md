# Competency Question System

The competency question system allows you to build and test questions that validate the NDA search system's effectiveness.

## Quick Start

### Load Questions from QA Pairs

The `eval/qa_pairs.json` file contains 30 pre-defined competency questions. Load them all:

```bash
# Using Make (recommended)
make load-questions

# Or directly
python3 scripts/load_competency_questions.py --use-db
```

### Run Tests

Test all loaded questions against your currently loaded documents:

```bash
# Using Make (recommended)
make test-questions

# Or directly
python3 scripts/load_competency_questions.py --test-only --test
```

### Load and Test in One Command

```bash
make load-and-test
```

## Script Options

The `scripts/load_competency_questions.py` script supports several options:

```bash
python3 scripts/load_competency_questions.py [OPTIONS]
```

### Options

- `--dry-run`: Preview what would be loaded without actually creating questions
- `--use-api`: Create questions via API (default)
- `--use-db`: Create questions directly in database (faster, recommended)
- `--test`: Run tests after loading questions
- `--test-only`: Only run tests, don't load questions
- `--document-id <ID>`: Test against a specific document ID

### Examples

```bash
# Preview what would be loaded
python3 scripts/load_competency_questions.py --dry-run

# Load questions using API
python3 scripts/load_competency_questions.py --use-api

# Load questions using DB and run tests
python3 scripts/load_competency_questions.py --use-db --test

# Test existing questions against a specific document
python3 scripts/load_competency_questions.py --test-only --test --document-id <document-id>
```

## Using the UI

### Question Builder

1. Navigate to `/competency/builder` in the UI
2. Questions loaded via the script will appear automatically
3. You can also create new questions manually
4. Click "Refresh" to reload the question list

### Test Runner

1. Navigate to `/competency/tester` in the UI
2. Select a question from the list
3. View the answer, citations, and response time
4. All loaded questions will be available for testing

## Test Results

The script provides a summary showing:
- Total questions tested
- Number passed/failed
- Pass rate percentage
- Response times
- Any errors encountered

A pass rate of 80%+ indicates the system is working well.

## QA Pairs Format

Questions are loaded from `eval/qa_pairs.json` which contains:

```json
{
  "id": "qa_001",
  "question": "What is the confidentiality period?",
  "expected_clause_keywords": ["confidentiality", "period", "term"],
  "expected_answer_type": "duration",
  "category": "term"
}
```

Currently, 30 questions are included covering:
- Confidentiality scope and definitions
- Terms and survival periods
- Exceptions and carve-outs
- Party obligations
- Remedies and dispute resolution
- And more...

## Notes

- Questions are created without category IDs (categories need to be set up separately)
- Tests verify that questions return answers with response times < 10 seconds
- All tests run against all currently loaded and processed documents
- The script automatically detects processed documents and warns if none are found

