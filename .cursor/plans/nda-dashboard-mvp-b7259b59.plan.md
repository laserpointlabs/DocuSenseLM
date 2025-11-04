<!-- b7259b59-af03-46bf-9838-b1491959c6d7 fcd334a0-ae38-4878-902a-187adf3e38e2 -->
# NDA Dashboard MVP Implementation Plan

## Architecture Overview

**Services:**

- `api/`: FastAPI service (upload, search, answer endpoints)
- `ingest/`: Background workers (PDF parsing, OCR, chunking, embedding, indexing)
- `ui/`: Next.js app (Search, Results, Document View, Admin)
- `infra/`: Terraform/CDK for AWS (OpenSearch, EC2/Qdrant, S3)
- `llm/`: Ollama/OpenAI integration layer
- `eval/`: Evaluation harness

**Local Stack (Docker Compose):**

- FastAPI (api)
- Ingest workers
- PostgreSQL (metadata)
- OpenSearch (single-node dev)
- Qdrant (single-node)
- MinIO (local S3-compatible)
- Next.js UI

## Component Breakdown

### 1. Infrastructure & Configuration

**Files:**

- `docker-compose.yml` - Local stack orchestration
- `.env.example` - All configuration variables
- `infra/terraform/main.tf` - AWS resources (OpenSearch, EC2, S3)
- `infra/cdk/` (alternative) - CDK implementation

**Key env vars:**

- `OPENSEARCH_URL`, `OPENSEARCH_USER`, `OPENSEARCH_PASS`
- `POSTGRES_URL`, `POSTGRES_USER`, `POSTGRES_PASS`
- `QDRANT_URL`
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
- `S3_BUCKET_RAW`, `S3_BUCKET_PROCESSED` (for AWS expansion)
- `EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2` (768-dim)
- `LLM_PROVIDER=ollama_local|ollama_network|openai`
- `LLM_ENDPOINT` (Ollama URL or OpenAI API endpoint)
- `OPENAI_API_KEY`
- `USE_TEXTRACT=false` (local) or `true` (prod)

### 2. Database Schema (PostgreSQL)

**Tables:**

- `documents` - id, filename, upload_date, status, s3_path, metadata_json
- `document_chunks` - id, document_id, chunk_index, section_type, clause_number, text, page_num, span_start, span_end
- `parties` - id, document_id, party_name, party_type (disclosing/receiving), address
- `document_metadata` - id, document_id, effective_date, governing_law, is_mutual, term_months, survival_months

**Indexes:**

- Foreign keys on document_id
- GIN index on metadata_json for JSON queries

### 3. Storage Layer (MinIO)

**Buckets:**

- `nda-raw` - Original uploaded files
- `nda-processed` - Extracted JSON (`nda_record.json` per document)
- `nda-logs` - Ingestion logs

**S3 Migration:**

- Shared interface (boto3 with MinIO endpoint override)
- Environment-based bucket selection

### 4. Ingestion Pipeline (`ingest/`)

**Modules:**

- `parser.py` - PDF/DOCX parsing (PyPDF2, python-docx)
- `ocr_detector.py` - Detect scanned vs native PDFs
- `ocr_local.py` - Tesseract integration (pytesseract)
- `ocr_aws.py` - Textract integration (optional)
- `clause_extractor.py` - Parse sections (title, recitals, numbered clauses, signatures)
- `chunker.py` - Clause-level chunking with provenance (source_uri, page_num, span_start, span_end)
- `embedder.py` - Generate 768-dim embeddings (sentence-transformers)
- `indexer_opensearch.py` - Index to OpenSearch (BM25 fields + metadata)
- `indexer_qdrant.py` - Index vectors to Qdrant with metadata
- `worker.py` - Main ingestion worker (Celery or async task queue)

**Flow:**

1. Accept PDF/DOCX → store in MinIO `nda-raw`
2. Detect if scanned → OCR (Tesseract/Textract) if needed
3. Parse into sections → extract parties, dates, clauses
4. Chunk at clause level → store in PostgreSQL `document_chunks`
5. Generate embeddings
6. Index to OpenSearch (BM25) + Qdrant (vectors)
7. Store normalized JSON in MinIO `nda-processed`

### 5. API Service (`api/`)

**FastAPI Structure:**

- `main.py` - FastAPI app, routes
- `models/` - Pydantic models (SearchRequest, AnswerRequest, DocumentResponse)
- `services/`:
  - `search_service.py` - Hybrid search (BM25 + vector), optional rerank
  - `answer_service.py` - LLM composition with citations
  - `storage_service.py` - MinIO/S3 operations
  - `db_service.py` - PostgreSQL queries
  - `competency_service.py` - Question management, test execution, metrics calculation
  - `ontology_service.py` - Ontology queries, entity extraction helpers
- `routers/`:
  - `upload.py` - POST /upload
  - `search.py` - POST /search
  - `answer.py` - POST /answer
  - `documents.py` - GET /documents/{id}, GET /documents
  - `admin.py` - POST /admin/reindex, GET /admin/stats
  - `competency.py` - Question CRUD, test execution, results, feedback
- `health.py` - GET /healthz

**Search Endpoint:**

- Accept query + filters (party, date_range, governing_law, is_mutual)
- Query OpenSearch (BM25, K=50) + Qdrant (vector, K=50)
- Merge results (score normalization)
- Optional cross-encoder rerank (top-N=10)
- Return with scores, metadata, spans

**Answer Endpoint:**

- Accept question + optional filters
- Run retrieval (same as search)
- Call LLM (Ollama/OpenAI) with context + query
- Return answer + citations (doc, clause, page, offsets)

### 6. LLM Integration (`llm/`)

**Modules:**

- `llm_client.py` - Abstract base class
- `ollama_client.py` - Ollama API client (local/network)
- `openai_client.py` - OpenAI API client
- `llm_factory.py` - Factory based on LLM_PROVIDER env var

**Interface:**

```python
async def generate_answer(query: str, context_chunks: List[Chunk], citations: List[Citation]) -> Answer
```

### 7. Frontend (`ui/`)

**Next.js Structure:**

- `app/` - App router (Next.js 13+)
  - `search/` - Search page
  - `results/` - Results page
  - `documents/[id]/` - Document view with clause highlighting
  - `admin/` - Admin dashboard
- `components/`:
  - `SearchBar.tsx` - Query input + starter questions
  - `ResultsList.tsx` - Hybrid results with scores
  - `DocumentViewer.tsx` - PDF viewer with clause highlighting
  - `CitationChip.tsx` - Citation badges
  - `AdminPanel.tsx` - Upload, re-index, stats
- `lib/` - API client, types
- `styles/` - Tailwind CSS

**Features:**

- Search page: query box + 25 starter questions (common NDA queries)
- Results: hybrid hits with badges (mutual/unilateral, term, survival)
- Document view: left TOC (clauses), right pane with highlighted spans
- Admin: upload, re-index, synonyms editor, stats

### 8. Evaluation Harness (`eval/`)

**Files:**

- `qa_pairs.json` - 20-30 QA pairs (questions → expected clause/field)
- `run_eval.py` - CLI script
- `metrics.py` - hit-rate@10, MRR, latency P95

**Metrics:**

- Hit-rate@10: % of queries where correct answer in top-10
- MRR: Mean Reciprocal Rank
- P95 latency: 95th percentile response time

### 9. Scripts

**Utilities:**

- `scripts/ingest_from_s3.py` - Batch ingest from S3 bucket
- `scripts/reindex.py` - Re-index all documents
- `scripts/seed_data.py` - Load 2-3 redacted NDAs for testing

### 10. Documentation

**README.md:**

- One-command dev setup (Docker Compose)
- Minimal Terraform snippets
- `.env.example` with all variables
- curl examples for search/answer
- Seed data instructions

## Implementation Order (MVP - All Local)

1. **Infrastructure** - Docker Compose (all local services), env config, PostgreSQL schema, MinIO setup
2. **Storage Layer** - MinIO client, PostgreSQL models, abstract interface for future S3 migration
3. **Ingestion Core** - PDF parsing, OCR detection (Tesseract only), clause extraction, chunking
4. **Embedding & Indexing** - Sentence transformers, Qdrant client, OpenSearch client
5. **API Service** - FastAPI structure, search/answer endpoints, LLM integration (Ollama/OpenAI)
6. **Frontend** - Next.js setup, search UI, results, document viewer
7. **Evaluation** - QA pairs, metrics, CLI
8. **Documentation** - README, examples, seed data, local setup instructions

**Post-MVP:** Infrastructure as Code (Terraform/CDK), Textract integration, S3 migration utilities

## Key Design Decisions

- **Local-first**: Docker Compose for all services, MinIO for file storage
- **AWS-ready**: S3 interface, Terraform for production deployment
- **Pluggable LLM**: Ollama (local/network) or OpenAI via env config
- **Hybrid search**: BM25 + vector (K=50 each), optional rerank
- **Clause-level retrieval**: Chunk at clause boundaries, precise citations
- **Testable**: Clean interfaces, evaluation harness, seed data

### To-dos

- [ ] Create Docker Compose file with PostgreSQL, OpenSearch, Qdrant, MinIO, and service definitions. Set up .env.example with all configuration variables.
- [ ] Design and implement PostgreSQL schema (documents, document_chunks, parties, document_metadata tables) with proper indexes and migrations.
- [ ] Implement MinIO client wrapper with S3-compatible interface. Create bucket management and file upload/download utilities.
- [ ] Build PDF/DOCX parser with OCR detection. Implement Tesseract (local) and Textract (AWS) integration modules.
- [ ] Implement clause extractor to parse NDA sections (title, recitals, numbered clauses, signature block) and extract metadata (parties, dates, governing law).
- [ ] Create clause-level chunking with provenance tracking. Implement 768-dim embedding generation using sentence-transformers/all-mpnet-base-v2.
- [ ] Implement OpenSearch indexing (BM25 with custom analyzers) and Qdrant indexing (vectors with metadata). Create indexer services.
- [ ] Build ingestion worker pipeline that orchestrates parsing → OCR → chunking → embedding → indexing. Store normalized JSON to MinIO.
- [ ] Create LLM client abstractions for Ollama (local/network) and OpenAI. Implement factory pattern for provider selection.
- [ ] Implement FastAPI search endpoint with hybrid retrieval (BM25 + vector, K=50 each), result merging, and optional rerank.
- [ ] Build answer endpoint that runs retrieval, assembles context, and calls LLM to generate answers with citations.
- [ ] Create upload endpoint, document retrieval endpoints, and admin endpoints (re-index, stats, health checks).
- [ ] Set up Next.js project with TypeScript, Tailwind CSS, and API client library. Create basic routing structure.
- [ ] Build search page with query input and starter questions. Create results page with hybrid hits, scores, and badges.
- [ ] Implement document viewer with left TOC (clauses), right pane with highlighted spans, and citation chips.
- [ ] Create admin panel with upload UI, re-index controls, synonyms editor, and basic statistics display.
- [ ] Create evaluation harness with 20-30 QA pairs, metrics calculation (hit-rate@10, MRR, P95 latency), and CLI script.
- [ ] Build utility scripts: ingest_from_s3.py, reindex.py, seed_data.py for batch operations and testing.
- [ ] Create minimal Terraform/CDK snippets for AWS resources (OpenSearch domain, EC2 for Qdrant, S3 buckets).
- [ ] Write comprehensive README with Docker Compose setup, env configuration, curl examples, seed data instructions, and deployment guide.