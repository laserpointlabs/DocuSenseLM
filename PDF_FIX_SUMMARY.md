# PDF Viewer Fix Summary

## Issues Fixed

1. **File Not Uploaded to Storage**: The file was only uploaded during ingestion, which failed. Now files are uploaded immediately during the upload endpoint.
2. **Document ID Mismatch**: Worker was creating new document IDs instead of using the one from the upload endpoint.
3. **Party Type Constraint**: Fixed null constraint violation by ensuring party_type is always set to 'disclosing' or 'receiving'.

## Changes Made

### `api/routers/upload.py`
- File is now uploaded to storage immediately during upload (before ingestion)
- Document s3_path is set right away
- Worker receives the correct document_id parameter

### `ingest/worker.py`
- Accepts `document_id` parameter to use existing document
- Only uploads file if not already uploaded
- Fixed party_type validation to ensure it's always 'disclosing' or 'receiving'

## For Existing Documents

If you have documents uploaded before this fix that don't have `s3_path` set, you have two options:

1. **Re-upload the document** (recommended)
2. **Wait for the ingestion to complete** - the worker will now upload the file if it's missing

## Next Steps

1. **Refresh the browser** to load the updated code
2. **Try viewing the document again** - it should now work
3. If it still doesn't work, the file may need to be re-uploaded

The PDF viewer should now work for newly uploaded documents. For the existing document, try refreshing the page or re-uploading it.
