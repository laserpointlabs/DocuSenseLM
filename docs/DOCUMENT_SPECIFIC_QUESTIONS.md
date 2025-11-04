# Document-Specific Competency Questions

## Overview

The system now supports **document-specific questions** that are generated from and verified against the actual loaded PDF documents. This ensures questions are relevant to your specific NDAs and can be verified by opening the source document.

## How It Works

1. **Question Generation**: Analyzes each loaded document to extract:
   - Effective date, term, survival period
   - Governing law
   - Mutual vs. unilateral status
   - Party names
   - Key clause titles (e.g., "Protection of Confidential Information", "Destruction of Materials")

2. **Question Creation**: Generates specific questions like:
   - "What is the effective date of the Norris Cylinder Company NDA?"
   - "What does the Protection of Confidential Information clause specify in the Norris Cylinder Company NDA?"
   - "What is the survival period after expiration for the Norris Cylinder Company NDA in months?"

3. **Verification Hints**: Each question includes:
   - **Verification Hint**: Instructions on where to find the answer (e.g., "Check clause 2 (Protection of Confidential Information) on page 1")
   - **Expected Clause**: The clause title where the answer should be found
   - **Expected Page**: The page number for quick verification

4. **Testing**: Questions can be tested against their specific document, and the Test Runner shows verification hints with links to view the source document.

## Usage

### Generate Questions for All Documents

```bash
# Generate and create questions for all loaded documents
python3 scripts/generate_document_questions.py --create --no-llm

# Preview what would be generated (dry run)
python3 scripts/generate_document_questions.py --dry-run
```

### Generate Questions for Specific Document

```bash
# Generate questions for Norris Cylinder Company document
python3 scripts/generate_document_questions.py --create --no-llm --document-id "a198d0f4-95bc-4a19-934e-130c95de2ffe"
```

### Using LLM to Generate Additional Questions

```bash
# Use LLM to generate contextual questions (requires LLM configured)
python3 scripts/generate_document_questions.py --create --use-llm
```

## Verification Workflow

1. **Run a Test**: In the Test Runner UI (`/competency/tester`), select a document-specific question
2. **View Answer**: The system generates an answer with citations
3. **Check Verification Hint**: The hint tells you exactly where to look:
   - "Check clause 2 (Protection of Confidential Information) on page 1 in Norris Cylinder Company_Signed NDA_expires Sept. 2028.pdf"
4. **Open Source Document**: Click "View Source Document" link to open the PDF
5. **Verify Answer**: Navigate to the specified clause and page to confirm the answer is correct

## UI Features

### Question Builder
- Document-specific questions are marked with "📄 Document-specific question"
- Questions auto-load when you open the builder

### Test Runner
- Shows verification hints for document-specific questions
- Provides direct link to view source document
- Citations are clickable links to the document viewer

## Example Questions Generated

For "Norris Cylinder Company_Signed NDA_expires Sept. 2028.pdf":

1. **"What is the effective date of the Norris Cylinder Company NDA?"**
   - Verification: "Check the effective date clause in Norris Cylinder Company_Signed NDA_expires Sept. 2028.pdf"

2. **"What does the Protection of Confidential Information clause specify in the Norris Cylinder Company NDA?"**
   - Verification: "Check clause 2 (Protection of Confidential Information) on page 1 in Norris Cylinder Company_Signed NDA_expires Sept. 2028.pdf"
   - Expected Clause: "Protection of Confidential Information"
   - Expected Page: 1

3. **"What is the survival period after expiration for the Norris Cylinder Company NDA in months?"**
   - Verification: "Check the survival clause in Norris Cylinder Company_Signed NDA_expires Sept. 2028.pdf"

## Benefits

- ✅ **Verifiable**: Every question can be verified by opening the source document
- ✅ **Document-Specific**: Questions are tailored to actual loaded documents
- ✅ **User-Friendly**: Clear hints tell users exactly where to find answers
- ✅ **Accurate Testing**: Tests validate the system against real documents, not generic questions

## Database Schema

The `competency_questions` table now includes:
- `document_id`: Links question to specific document
- `verification_hint`: Instructions for verifying the answer
- `expected_clause`: Expected clause title/number
- `expected_page`: Expected page number

## Testing Document-Specific Questions

When you run a test for a document-specific question:
1. The system automatically filters search results to that document
2. The answer is generated from that document's content
3. Citations point to specific clauses in that document
4. You can click through to verify the answer is correct

This ensures questions are **actually testable** against real documents, not just random questions that might or might not have answers in your corpus.

