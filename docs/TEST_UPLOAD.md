# Upload Endpoint Testing

## Test Results

The upload endpoint works correctly when tested with curl:

```bash
curl -X POST http://localhost:8000/upload -F "file=@test.pdf"
```

**Response:**
```json
{
  "document_id": "...",
  "filename": "test.pdf",
  "status": "uploaded",
  "message": "File uploaded. Processing in background."
}
```

## UI Fix

Updated `ui/lib/api.ts` to use axios directly with the full URL instead of the api instance, which should fix FormData issues.

## Next Steps

1. Refresh the UI at http://localhost:3000/admin
2. Try uploading a file again
3. Check browser console for any errors

If 422 still occurs, check the API logs for validation error details.
