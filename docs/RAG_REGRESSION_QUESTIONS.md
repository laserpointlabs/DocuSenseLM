# RAG Regression Questions (Example Corpus + OCR)

This file defines a **golden question suite** you can use to regression-test RAG quality and stability across releases.

## How to Use

- **Manual**: Upload the listed documents (your production corpus) and ask the questions in-app. Verify the answer contains the expected facts and cites the expected document.
- **Automated**: Run `pytest tests/test_rag_golden_questions.py -v` with the backend running on `localhost:14242`.

## A) Example Corpus (Regular PDFs)

These questions are based on the **currently processed documents** returned by `GET /documents`.

> Note: In the public repo, we intentionally use **generic example document names** (no real company/vendor names).
> Replace these with your own internal corpus filenames if you maintain a private/internal version of this suite.

| ID | Document(s) | Question | Expected (must contain) | Expected Source | Current Response (baseline) |
|---|---|---|---|---|---|
| example_weeding_rate | `example_maintenance_agreement.pdf` | What do we pay for weeding? | `$55` and `(per man hour\|per man, per man hour\|T&M\|Time and Material)` | `example_maintenance` | The cost for weeding is $55.00 per man, per man hour, plus dumping fees. |
| example_seasonal_price | `example_maintenance_agreement.pdf` | What is the seasonal contract price? | `$15,000` | `example_maintenance` | The seasonal contract price is $15,000.00. |
| example_nda_parties | `example_nda.pdf` | Who are the parties? | `Acme` and `Beta` | `example_nda` | The parties are Acme and Beta. |
| example_expiration | `example_nda.pdf` | What is the expiration date? | `July` and `2028` | `example_nda` | The expiration date is July 31, 2028. |

## B) OCR/Scanned PDF Regression (Synthetic Docs)

Your current production corpus is all `text_extracted=true`. To ensure OCR is always exercised, we include two **synthetic scanned PDFs** (image-only) that should be uploaded to production as well.

### Generate OCR regression PDFs

Run this once:

```bash
python tests/fixtures/generate_scanned_test_pdfs.py
```

This will create:
- `tests/fixtures/scanned_pricing_test.pdf`
- `tests/fixtures/scanned_nda_test.pdf`

Upload them like any other document and ensure they process to `text_extracted=true`.

| ID | Document | Question | Expected (must contain) | Expected Source | Current Response (baseline) |
|---|---|---|---|---|---|
| ocr_pricing_weeding | `scanned_pricing_test.pdf` | What do we pay for weeding? | `$55` | `scanned_pricing_test` | (Populate after uploading the OCR fixtures and re-running the question.) |
| ocr_nda_parties | `scanned_nda_test.pdf` | Who are the parties? | `Acme` and `Beta` | `scanned_nda_test` | (Populate after uploading the OCR fixtures and re-running the question.) |
