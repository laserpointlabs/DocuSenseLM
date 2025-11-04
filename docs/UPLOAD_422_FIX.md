# Fixed 422 Unprocessable Entity Error

## Issues Fixed

1. **Indentation Problem**: Fixed the try/except block structure in `upload.py` that was causing validation issues
2. **Enum Comparison Bug**: Fixed `db_service.py` to use `DocumentStatus.PROCESSED` enum instead of string `'processed'`

## Changes Made

### `api/routers/upload.py`
- Removed incorrect try block indentation
- Proper exception handling structure

### `api/services/db_service.py`
- Added `DocumentStatus` import
- Changed `Document.status == 'processed'` to `Document.status == DocumentStatus.PROCESSED`

## Testing

The upload endpoint should now work correctly:
- Accepts PDF and DOCX files
- Rejects other file types with 400 error (not 422)
- Properly creates document records in database

Try uploading a PDF file from the UI at http://localhost:3000/admin

