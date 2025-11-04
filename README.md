# NDA Dashboard MVP

A single-tenant NDA Dashboard for ingesting, searching, and analyzing Non-Disclosure Agreements using hybrid search (BM25 + vector) and LLM-powered question answering.

## Features

- **Hybrid Search**: Combines OpenSearch BM25 and Qdrant vector search for optimal retrieval
- **LLM Integration**: Supports Ollama (local/network) and OpenAI for answer generation
- **Clause-Level Retrieval**: Chunk documents at clause level with precise citations
- **Competency Question System**: Build and test questions to validate system effectiveness
- **Ontology-Driven**: Structured knowledge model for NDA domain concepts
- **Local-First**: All services run locally via Docker Compose (no AWS required for MVP)

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Next.js   │────▶│   FastAPI   │────▶│  PostgreSQL │
│     UI      │     │     API     │     │   Database  │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐  ┌────────▼───────┐  ┌──────▼──────┐
│  OpenSearch  │  │    Qdrant     │  │    MinIO    │
│   (BM25)     │  │   (Vectors)   │  │  (Storage)  │
└──────────────┘  └────────────────┘  └──────────────┘
        │
┌───────▼──────┐
│   Ingestion  │
│   Pipeline   │
└──────────────┘
```

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 20+ (for local frontend development)
- Ollama (optional, for local LLM) - Install from [ollama.ai](https://ollama.ai)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd ndaTool
cp .env.example .env
# Edit .env with your configuration
```

### 2. Start Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432)
- OpenSearch (port 9200)
- Qdrant (port 6333)
- MinIO (ports 9000, 9001)
- FastAPI API (port 8000)
- Next.js UI (port 3000)

### 3. Initialize Database

```bash
docker-compose exec api python api/db/migrations/001_init_schema.py
```

### 4. Seed Sample Data (Optional)

```bash
docker-compose exec api python scripts/seed_data.py
```

### 5. Access the Application

- **UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

## Configuration

Key environment variables (see `.env.example`):

```bash
# LLM Configuration
LLM_PROVIDER=ollama_local          # Options: ollama_local, ollama_network, openai
LLM_ENDPOINT=http://localhost:11434
OPENAI_API_KEY=                    # Required if using OpenAI

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2  # 768-dim

# OCR Configuration
USE_TEXTRACT=false                  # true for AWS Textract, false for Tesseract
```

## Usage

### Upload Documents

1. Navigate to Admin page: http://localhost:3000/admin
2. Click "Choose File" and select a PDF or DOCX file
3. Upload starts processing in the background

### Search Documents

1. Go to Search page: http://localhost:3000/search
2. Enter a query or click a starter question
3. View results with scores and citations

### Ask Questions

1. Go to Answer page: http://localhost:3000/answer
2. Enter your question
3. Get AI-generated answer with citations

### Competency Testing

1. Go to Competency → Builder: Create test questions
2. Go to Competency → Tester: Run tests and view metrics

## API Examples

### Search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the confidentiality period?",
    "k": 50
  }'
```

### Answer

```bash
curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What information is considered confidential?",
    "max_context_chunks": 10
  }'
```

### Upload

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@document.pdf"
```

## Evaluation

Run the evaluation harness:

```bash
docker-compose exec api python eval/run_eval.py --verbose
```

This runs 30 QA pairs and calculates:
- Hit Rate @ 10
- Mean Reciprocal Rank (MRR)
- Precision/Recall @ 10
- Latency percentiles (P50, P95, P99)

## Scripts

### Batch Ingest from S3

```bash
python scripts/ingest_from_s3.py my-bucket --prefix "ndas/" --limit 100
```

### Re-index Documents

```bash
# Re-index all documents
python scripts/reindex.py --all

# Re-index specific document
python scripts/reindex.py --document-id <uuid>
```

### Seed Sample Data

```bash
python scripts/seed_data.py --docs-dir docs
```

## Development

### Running Locally (without Docker)

1. **Start Services**:
   ```bash
   docker-compose up -d postgres opensearch qdrant minio
   ```

2. **API**:
   ```bash
   cd api
   pip install -r ../requirements.txt
   python -m uvicorn api.main:app --reload
   ```

3. **Frontend**:
   ```bash
   cd ui
   npm install
   npm run dev
   ```

## Project Structure

```
ndaTool/
├── api/                 # FastAPI backend
│   ├── main.py         # FastAPI app
│   ├── routers/        # API endpoints
│   ├── services/       # Business logic
│   └── models/         # Pydantic models
├── ingest/             # Ingestion pipeline
│   ├── parser.py       # PDF/DOCX parsing
│   ├── ocr_*.py        # OCR implementations
│   ├── clause_extractor.py
│   ├── chunker.py
│   ├── embedder.py
│   └── indexer_*.py    # Search indexers
├── llm/                # LLM integration
│   ├── ollama_client.py
│   └── openai_client.py
├── ontology/           # NDA ontology
├── ui/                 # Next.js frontend
│   ├── app/            # Pages
│   └── components/     # React components
├── eval/               # Evaluation harness
├── scripts/            # Utility scripts
└── docker-compose.yml
```

## Ingestion Pipeline

1. **Upload** → Store in MinIO `nda-raw` bucket
2. **Parse** → Extract text from PDF/DOCX
3. **OCR** → If scanned, use Tesseract (local) or Textract (AWS)
4. **Extract** → Parse clauses, parties, dates, metadata
5. **Chunk** → Clause-level chunking with provenance
6. **Embed** → Generate 768-dim embeddings
7. **Index** → Index to OpenSearch (BM25) + Qdrant (vectors)
8. **Store** → Save normalized JSON to MinIO `nda-processed`

## Competency Question System

The competency system allows you to:
- **Build Questions**: Create test questions with LLM assistance
- **Define Ground Truth**: Specify expected answers/clauses
- **Run Tests**: Execute questions against the system
- **Track Metrics**: Monitor accuracy over time
- **Provide Feedback**: Refine ground truth based on results

## Troubleshooting

### OpenSearch not starting
- Ensure Docker has at least 4GB RAM allocated
- Check logs: `docker-compose logs opensearch`

### Qdrant connection errors
- Verify Qdrant is healthy: `curl http://localhost:6333/health`
- Check network connectivity between services

### LLM not responding
- For Ollama: Ensure Ollama is running (`ollama serve`)
- Check `LLM_ENDPOINT` in `.env`
- For OpenAI: Verify `OPENAI_API_KEY` is set

### Embedding model download
- First run downloads the model (~420MB)
- Ensure sufficient disk space and network bandwidth

## Next Steps (Post-MVP)

- [ ] AWS Infrastructure (Terraform/CDK)
- [ ] Enhanced PDF viewer with clause highlighting
- [ ] Metrics visualization dashboard
- [ ] User authentication
- [ ] Multi-tenant support
- [ ] Advanced reranking (cross-encoder)

## License

[Your License Here]

## Support

For issues or questions, please open an issue in the repository.
