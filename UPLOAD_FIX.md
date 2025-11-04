# Upload Fix Summary

## Issues Fixed

1. **Database Session Error**: Changed `next(get_db_session())` to `get_db_session()` in all routers
   - `get_db_session()` returns a Session directly, not a generator
   - Fixed in: `upload.py`, `documents.py`, `admin.py`, `competency.py`

2. **FormData Upload Issue**: Removed explicit `Content-Type: multipart/form-data` header
   - Axios needs to set the Content-Type with the boundary parameter automatically
   - Fixed in: `ui/lib/api.ts`

## Testing

To test the upload:
1. Go to http://localhost:3000/admin
2. Click "Choose File"
3. Select a PDF or DOCX file
4. The file should upload successfully

The API endpoint is working correctly and accepts PDF and DOCX files.
