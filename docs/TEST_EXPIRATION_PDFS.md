# Test Expiration PDFs

This document describes the test PDFs created for testing expiration detection in the NDA Dashboard.

## Overview

Test PDFs have been generated to verify that the system can properly detect and flag:
- **Near-expiration NDAs**: Documents expiring within 30, 60, and 90 days
- **Expired NDAs**: Documents that have already expired (30 and 60 days ago)

## Generated Test PDFs

### Near Expiration (30-90 days)

These PDFs will help test the "Expiring Soon" filter and alerts:

1. **Delva Tool & Machine, LLC**
   - `Delva Tool & Machine, LLC_Signed NDA_Expires Dec. 2025.pdf` - ~30 days
   - `Delva Tool & Machine, LLC_Signed NDA_Expires Jan. 2026.pdf` - ~60 days
   - `Delva Tool & Machine, LLC_Signed NDA_Expires Feb. 2026.pdf` - ~90 days

2. **Norris Cylinder Company**
   - `Norris Cylinder Company_Signed NDA_Expires Dec. 2025.pdf` - ~30 days
   - `Norris Cylinder Company_Signed NDA_Expires Jan. 2026.pdf` - ~60 days
   - `Norris Cylinder Company_Signed NDA_Expires Feb. 2026.pdf` - ~90 days

### Expired (30-60 days ago)

These PDFs will help test the "Expired" filter:

1. **Delva Tool & Machine, LLC**
   - `Delva Tool & Machine, LLC_Signed NDA_Expires Oct. 2025.pdf` - expired ~30 days ago
   - `Delva Tool & Machine, LLC_Signed NDA_Expires Sept. 2025.pdf` - expired ~60 days ago

2. **Norris Cylinder Company**
   - `Norris Cylinder Company_Signed NDA_Expires Oct. 2025.pdf` - expired ~30 days ago
   - `Norris Cylinder Company_Signed NDA_Expires Sept. 2025.pdf` - expired ~60 days ago

## Testing Instructions

### 1. Upload Test PDFs

1. Log in to the NDA Dashboard as admin
2. Navigate to the Admin page
3. Upload the test PDFs (you can select multiple files)
4. Wait for processing to complete

### 2. Verify Expiration Detection

1. Go to the Dashboard page
2. Check the statistics cards:
   - **Expiring Soon**: Should show the count of near-expiration NDAs
   - **Expired**: Should show the count of expired NDAs

3. Test the filters:
   - Select "Expiring Soon" filter - should show 6 documents
   - Select "Expired" filter - should show 4 documents

4. Verify expiration status in the table:
   - Documents should show correct expiration dates
   - Status should indicate "Expiring Soon" or "Expired" appropriately

### 3. Test Search and Questions

1. **Search for expiring documents:**
   - Search for "expiring soon" or "expiration"
   - Verify results include the test PDFs

2. **Ask questions about expiration:**
   - "Which NDAs are expiring soon?"
   - "What NDAs have expired?"
   - "When does the Delva Tool & Machine NDA expire?"

## Regenerating Test PDFs

If you need to regenerate the test PDFs (e.g., after time passes), run:

```bash
python3 scripts/generate_test_expiration_pdfs.py
```

**Note**: This script will create new PDFs with updated dates based on the current date. Old test PDFs will be overwritten.

## Expected Behavior

### Dashboard Display

- **Near-expiration NDAs** should:
  - Appear in "Expiring Soon" filter
  - Show days remaining (e.g., "30 days remaining")
  - Be highlighted or flagged appropriately

- **Expired NDAs** should:
  - Appear in "Expired" filter
  - Show as expired status
  - Be clearly marked as expired

### Date Calculations

The system calculates expiration dates from:
1. Filename parsing (e.g., "Expires Dec. 2025")
2. Document metadata extraction (effective_date + term_months)
3. Explicit expiration date fields in the document

## Troubleshooting

### PDFs Not Showing Correct Expiration Status

1. **Check filename format:**
   - Ensure filenames follow the pattern: `Company_Signed NDA_Expires Month. Year.pdf`
   - Month abbreviations: Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sept, Oct, Nov, Dec

2. **Verify document processing:**
   - Check Admin page to ensure documents are "Processed" status
   - Review document metadata extraction

3. **Check date parsing:**
   - The system extracts dates from filenames and document content
   - Verify the expiration date is being parsed correctly

### Dates Not Updating

- Expiration dates are calculated when documents are processed
- If dates change, you may need to re-process the documents
- Use the "Re-index All Documents" button on the Admin page if needed

## File Locations

- **Test PDFs**: `data/` directory
- **Generation Script**: `scripts/generate_test_expiration_pdfs.py`
- **Documentation**: `docs/TEST_EXPIRATION_PDFS.md`

## Notes

- Test PDFs are copies of existing NDAs with modified filenames
- The PDF content itself is not modified (only filenames)
- The system relies on filename parsing and metadata extraction for expiration dates
- Actual expiration dates in the PDF content may differ from filename dates

