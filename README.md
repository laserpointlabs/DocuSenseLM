# NDA Dashboard MVP

A single-tenant NDA Dashboard for ingesting, searching, and analyzing Non-Disclosure Agreements using hybrid search (BM25 + vector) and LLM-powered question answering.

## Features

- **Hybrid Search**: Combines OpenSearch BM25 and Qdrant vector search for optimal retrieval
- **LLM Integration**: Supports Ollama (local/network) and OpenAI for answer generation
- **Clause-Level Retrieval**: Chunk documents at clause level with precise citations
- **Competency Question System**: Build and test questions to validate system effectiveness
- **Ontology-Driven**: Structured knowledge model for NDA domain concepts
- **Deterministic NDA Registry**: Track signed agreements, run lifecycle checks, and emit expiring/expired events
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

> **Note on model downloads**
> The first ingestion run downloads the sentence-transformers model (~438 MB).
> A shared cache is mounted at `./.cache/huggingface`, so subsequent rebuilds reuse the model.
> Keep this folder if you want faster restarts.

### 3. Initialize Database

```bash
# Tables are created automatically, but you can also run:
docker compose exec -T api python -c "from api.db import init_db; init_db()"
```

### 4. Create Initial Users

```bash
# Create default admin and usermgt users
docker compose exec -T api python scripts/create_users.py
```

**Default Credentials:**
- Admin: `admin` / `Admin2024!Secure`
- UserMgt: `usermgt` / `UserMgt2024!Secure`

**⚠️ Important**: Change these passwords immediately after first setup!

See [User Management Guide](docs/USER_MANAGEMENT.md) for detailed user management instructions.

### 5. Seed Sample Data (Optional)

```bash
docker-compose exec api python scripts/seed_data.py
```

### 6. Access the Application

- **UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

### 7. Expose via Cloudflare Tunnel (Optional)

To host this application from home and make it accessible from the internet:

1. **Run the setup script**:
   ```bash
   ./scripts/setup_cloudflare_tunnel.sh
   ```
   This will guide you through creating a Cloudflare Tunnel and configuring DNS.

2. **Or manually configure**:
   - See [cloudflare/README.md](cloudflare/README.md) for detailed instructions
   - Add Cloudflare Tunnel environment variables to your `.env` file:
     ```bash
     CLOUDFLARE_TUNNEL_TOKEN=<your-tunnel-token>
     CLOUDFLARE_DOMAIN_UI=ui.yourdomain.com
     CLOUDFLARE_DOMAIN_API=api.yourdomain.com
     ```

3. **Start services** (the cloudflared service will start automatically):
   ```bash
   docker-compose up -d
   ```

4. **Access via your domain**:
   - **UI**: https://ui.yourdomain.com
   - **API**: https://api.yourdomain.com

## Configuration

Key environment variables (see [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md) for complete reference):

```bash
# LLM Configuration
LLM_PROVIDER=ollama_local          # Options: ollama_local, ollama_network, openai
LLM_ENDPOINT=http://localhost:11434
OPENAI_API_KEY=                    # Required if using OpenAI

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2  # 768-dim

# OCR Configuration
USE_TEXTRACT=false                  # true for AWS Textract, false for Tesseract

# Email Configuration (see docs/ENVIRONMENT_VARIABLES.md for all options)
EMAIL_SMTP_HOST=mailhog            # SMTP server (mailhog for local dev)
EMAIL_SMTP_PORT=1025               # SMTP port
EMAIL_FROM_ADDRESS=nda-system@example.com
EMAIL_POLLER_ENABLED=true          # Enable email polling worker
EMAIL_POLL_INTERVAL=60             # Poll interval in seconds

# Workflow Configuration
CAMUNDA_URL=http://camunda:8080   # Camunda BPMN engine URL
WORKFLOW_LLM_REVIEW_ENABLED=true  # Enable LLM review of NDAs

# Cloudflare Tunnel (optional)
CLOUDFLARE_TUNNEL_TOKEN=            # Tunnel token from Cloudflare Dashboard
CLOUDFLARE_DOMAIN_UI=ui.yourdomain.com
CLOUDFLARE_DOMAIN_API=api.yourdomain.com
```

For complete environment variable documentation, see [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md).

## Usage

### Authentication

The NDA Dashboard requires authentication to access. After starting the services:

1. Navigate to `http://localhost:3000`
2. You'll be redirected to the login page
3. Log in with your credentials (default: `admin` / `Admin2024!Secure`)

For user management, password updates, and account administration, see the [User Management Guide](docs/USER_MANAGEMENT.md).

### Upload Documents

1. Navigate to Admin page: http://localhost:3000/admin
2. Click "Choose File" and select a PDF or DOCX file
3. Upload starts processing in the background

> ℹ️ **LLM Refinement (optional)**
> By default the pipeline relies on the heuristic extractor. Set `ENABLE_LLM_REFINEMENT=true`
> (and expose `LLM_ENDPOINT`, e.g. `http://host.docker.internal:11434`) if you want a local
> Ollama model to fill in missing party addresses or other metadata. Ensure Ollama is started with
> `OLLAMA_HOST=0.0.0.0` (listening on all interfaces) so the Docker containers can reach it.

### Search Documents

1. Go to Search page: http://localhost:3000/search
2. Enter a query or click a starter question
3. View results with scores and citations

### Ask Questions

1. Go to Answer page: http://localhost:3000/answer
2. Enter your question
3. Get AI-generated answer with citations

### Reset & Reseed the Stack

When you need a clean slate (fresh databases, storage, and sample docs):

```bash
python scripts/reset_environment.py
```

The script tears everything down, recreates containers, runs migrations, and re-ingests the sample PDFs from `data/`. Use `--skip-build` to reuse existing images, `--docs-dir` to point at a different corpus, and `--load-competency` to auto-populate competency questions.

### Faster Docker Builds

BuildKit caching is enabled in the Dockerfiles. For noticeably faster rebuilds (especially after small code changes), use:

```bash
DOCKER_BUILDKIT=1 docker compose build --parallel
```

This reuses cached apt/pip/npm layers across services instead of reinstalling every time.

### Competency Testing

1. Go to Competency → Builder: Create test questions
2. Go to Competency → Tester: Run tests and view metrics

## API Examples

### Registry

```bash
# Check if an NDA is active for a counterparty
curl "http://localhost:8000/registry/check?domain=acme.com"

# Search the structured NDA registry
curl "http://localhost:8000/registry/search?query=Delaware"

# List NDAs expiring in the next 60 days
curl "http://localhost:8000/registry/expiring?window_days=60"
```

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

Compare reranker strategies (baseline vs RRF) and write summary metrics:

```bash
docker-compose exec api python eval/compare_rag.py --output /tmp/rerank_summary.json
```

This runs 30 QA pairs and calculates:
- Hit Rate @ 10
- Mean Reciprocal Rank (MRR)
- Precision/Recall @ 10
- Latency percentiles (P50, P95, P99)

Example (write metrics to JSON for benchmarking):

```bash
docker-compose exec api python eval/run_eval.py --k 20 --output /tmp/rag_eval.json
```

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

### RAG Audit & Retrieval Benchmarks

```bash
# Summarize chunk/metadata statistics stored in the DB
python scripts/rag_audit.py --output /tmp/rag_stats.json

# Compare reranker strategies (e.g., none vs RRF) and export metrics
docker-compose exec api python eval/compare_rag.py --output /tmp/rerank_summary.json
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

4. **Run Tests**:
   ```bash
   pytest
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
