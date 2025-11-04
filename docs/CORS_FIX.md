# CORS and Error Handling Fix

## Issues Fixed

1. **CORS Headers Missing on Errors**: Added exception handlers to ensure CORS headers are always included, even when errors occur
2. **Database Session Bug**: Fixed `next(get_db_session())` in `ingest/worker.py` (3 occurrences)

## Changes Made

### `api/main.py`
- Added exception handlers for:
  - `StarletteHTTPException` (HTTP errors)
  - `RequestValidationError` (422 validation errors)
  - `Exception` (general 500 errors)
- All handlers now include `Access-Control-Allow-Origin: *` header
- Added `expose_headers=["*"]` to CORS middleware

### `ingest/worker.py`
- Changed `next(get_db_session())` to `get_db_session()` in 3 places
- Fixed lines: 116, 220, 234

## Testing

The API should now:
- ✅ Return CORS headers on all responses (including errors)
- ✅ Handle `/admin/stats` requests correctly
- ✅ Allow file uploads from the UI
- ✅ Work properly from http://localhost:3000

Try refreshing the admin page at http://localhost:3000/admin
