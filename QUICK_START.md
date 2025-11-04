# Quick Start Guide

## Access Points

- **UI**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

## Current Configuration

- **LLM Provider**: OpenAI (configured in `.env`)
- **Embedding Model**: sentence-transformers/all-mpnet-base-v2
- **Storage**: MinIO (local S3-compatible)

## Using OpenAI

The system is configured to use OpenAI. Your API key is already set in the environment.

To verify it's working, test the answer endpoint:

```bash
curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the confidentiality period?"}'
```

## Upload a Document

1. Go to http://localhost:3000/admin
2. Click "Choose File" and select a PDF
3. Upload the document
4. Wait for processing (check status in admin panel)

## Search Documents

1. Go to http://localhost:3000/search
2. Enter a query or click a starter question
3. View results with scores and citations
