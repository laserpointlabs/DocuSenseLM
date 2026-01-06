# RAG Regression Questions (Production Corpus + OCR)

This file defines a **golden question suite** you can use to regression-test RAG quality and stability across releases.

## How to Use

- **Manual**: Upload the listed documents (your production corpus) and ask the questions in-app. Verify the answer contains the expected facts and cites the expected document.
- **Automated**: Run `pytest tests/test_rag_golden_questions.py -v` with the backend running on `localhost:14242`.

## A) Production Corpus (Regular PDFs)

These questions are based on the **currently processed documents** returned by `GET /documents`.

| ID | Document(s) | Question | Expected (must contain) | Expected Source | Current Response (baseline) |
|---|---|---|---|---|---|
| franny_weeding_rate | `2024 Franny's MAINTENANCE AGREEMENT_Signed.pdf` | What do we pay for weeding? | `$55` and `(per man hour\|per man, per man hour\|T&M\|Time and Material)` | `Franny` + `MAINTENANCE` | The cost for weeding is $55.00 per man, per man hour, plus dumping fees. *(Note: the line item in the PDF is labeled T&M / Time and Material, but the model may or may not include that label in the phrasing.)* |
| franny_maintenance_seasonal_price | `2024 Franny's MAINTENANCE AGREEMENT_Signed.pdf` | What is the seasonal contract price in the Franny maintenance agreement? | `$15,000` | `Franny` + `MAINTENANCE` | The seasonal contract price in the Franny maintenance agreement is $15,000.00. |
| franny_snow_total | `2024-2025 Frannys Snow Contract_Signed.pdf` | What do we pay Franny's for snow removal? | `$49,000` and `$9,800` | `Frannys Snow Contract` | For snow removal, Franny's provides a seasonal lump sum pricing service totaling $49,000.00, with five equal payments of $9,800.00 each month (November through March). After 70 inches, the contract reverts to hourly pricing; salt applications after the 70-inch threshold cost $1,000.00 per application. |
| franny_snow_payments | `2024-2025 Frannys Snow Contract_Signed.pdf` | How many payments are there for the Franny snow contract and how much is each payment? | `five` and `$9,800` | `Frannys Snow Contract` | There are five equal payments for the season, and each payment is $9,800.00. |
| franny_snow_salt | `2024-2025 Frannys Snow Contract_Signed.pdf` | What is the cost per salt application in the Franny snow contract (after the 70-inch threshold)? | `$1,000` | `Frannys Snow Contract` | The cost per salt application after the 70-inch threshold is $1,000.00 per application. |
| nda_fanuc_parties | `Fanuc America Corporation_Signed NDA_Expires June 2028.pdf` | Who are the parties in the Fanuc America Corporation NDA? | `Fanuc` and `Kidde` | `Fanuc America Corporation` | The parties in the Fanuc America Corporation NDA are Fanuc America Corporation and Kidde-Fenwal, LLC. |
| nda_kgs_parties | `KGS Fire & Security B.V._Signed NDA_Expires Sept. 2028.pdf` | Who are the parties in the KGS Fire and Security B.V. NDA? | `KGS` and `Kidde` | `KGS Fire` | The parties in the KGS Fire and Security B.V. NDA are KGS Fire & Security B.V. and Kidde-Fenwal, LLC, and their affiliates. |
| worthington_expiration | `WORTHINGTON_SALES_AGREEMENT_-_07JUL2025 - signed_expires July 31 2028.pdf` | What is the expiration date of the WORTHINGTON sales agreement? | `July` and `2028` | `WORTHINGTON` | The WORTHINGTON sales agreement expires on July 31, 2028. |

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
