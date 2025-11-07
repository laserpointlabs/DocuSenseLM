<!-- f25e8376-bc2c-44f4-93f8-effcd322c3c5 4b2c8762-ee34-4420-8ff0-17611c3debe1 -->
# Rebuild RAG System for 95%+ Accuracy

## Problem Analysis

Current system has 26.7% pass rate and 33% accuracy. Key issues:

1. **Terrible prompt**: Ollama uses basic prompt vs OpenAI's structured format rules
2. **Metadata not used**: Structured metadata (effective_date, governing_law, parties, term, is_mutual) exists but isn't leveraged
3. **No query understanding**: Basic topic extraction only
4. **No cross-document reasoning**: Can't answer questions across multiple documents
5. **Poor extraction**: LLM doesn't extract structured data correctly

## Solution Strategy (Based on Best Practices)

### Phase 1: Metadata-First Retrieval for Structured Fields

**Best Practice**: For similar documents with similar key data, use metadata-first approach for structured fields, then fall back to chunk retrieval for complex questions.

**Implementation**:

- Create `api/services/metadata_service.py` to query DocumentMetadata table
- Detect structured questions (effective_date, governing_law, term, parties, is_mutual)
- For structured questions: Query metadata first, return directly if found
- For complex questions: Use hybrid retrieval, but enhance with metadata context
- Files to modify:
- `api/services/answer_service.py`: Add metadata-first logic
- `api/services/metadata_service.py`: New service for metadata queries
- `api/db/schema.py`: Already has DocumentMetadata table

### Phase 2: Enhanced Prompt Engineering

**Best Practice**: Use structured format rules with few-shot examples and explicit extraction instructions.

**Implementation**:

- Replace basic Ollama prompt with structured format rules (like OpenAI client)
- Add few-shot examples for each question type
- Add explicit extraction instructions
- Add cross-document synthesis instructions
- **Centralize all prompts** in `llm/prompts.py` for easy review and maintenance
- Both OpenAI and Ollama clients use the same centralized prompts
- Files to modify:
- `llm/ollama_client.py`: Complete prompt rewrite to use centralized prompts
- `llm/openai_client.py`: Update to use centralized prompts (remove duplicate code)
- Create `llm/prompts.py`: Centralized prompt templates (single source of truth)

### Phase 3: Contextual Embeddings

**Best Practice**: Prepend contextual information (metadata, document title, clause title) to chunks before embedding.

**Implementation**:

- Enhance chunk text with metadata context before embedding
- Format: `[Document: {filename}, Parties: {parties}, Governing Law: {governing_law}] {chunk_text}`
- Files to modify:
- `ingest/indexer_qdrant.py`: Enhance chunks with metadata before embedding
- `ingest/indexer_opensearch.py`: Add metadata to BM25 index

### Phase 4: Query Understanding and Transformation

**Best Practice**: Implement query expansion and reformulation for better retrieval.

**Implementation**:

- Create `api/services/query_service.py` for query understanding
- Detect question type (structured vs complex, single-doc vs cross-doc)
- Expand queries with synonyms and related terms
- Transform queries for better retrieval (e.g., "governing state of Vallen" -> "governing law Vallen Distribution")
- Files to modify:
- `api/services/query_service.py`: New service
- `api/services/answer_service.py`: Use query service

### Phase 5: Cross-Document Synthesis

**Best Practice**: Retrieve from multiple documents and synthesize in one prompt with clear document separation.

**Implementation**:

- Detect cross-document queries (e.g., "compare", "across all", "all NDAs")
- Retrieve chunks from multiple documents
- Format context with clear document boundaries
- Add synthesis instructions to prompt
- Files to modify:
- `api/services/answer_service.py`: Add cross-doc detection and synthesis
- `llm/ollama_client.py`: Add cross-doc prompt section

### Phase 6: Chunk Quality Assessment and Reranking

**Best Practice**: Assess chunk quality before sending to LLM, rerank for relevance.

**Implementation**:

- Add chunk quality scoring (relevance, completeness, answer presence)
- Filter low-quality chunks
- Enhance reranking with answer presence detection
- Files to modify:
- `api/services/answer_service.py`: Add chunk quality assessment
- `api/services/rerank.py`: Enhance reranking logic

### Phase 7: Testing and Validation

**Implementation**:

- Update test suite to validate metadata-first approach
- Add tests for cross-document queries
- Validate 95%+ accuracy on golden questions
- Files to modify:
- `scripts/rag_test_suite.py`: Add metadata-first tests
- Create `scripts/test_metadata_retrieval.py`: Test metadata service

## Implementation Order

1. **Phase 1** (Metadata-First): Highest impact, fastest to implement
2. **Phase 2** (Prompt Engineering): Critical for accuracy
3. **Phase 3** (Contextual Embeddings): Requires re-indexing but improves retrieval
4. **Phase 4** (Query Understanding): Improves retrieval quality
5. **Phase 5** (Cross-Document): Enables new capabilities
6. **Phase 6** (Chunk Quality): Fine-tuning
7. **Phase 7** (Testing): Validation

## Expected Outcomes

- **95%+ accuracy** on structured questions using metadata-first approach
- **80%+ accuracy** on complex questions with enhanced prompts
- **Cross-document queries** working for comparison questions
- **Faster responses** for structured questions (metadata lookup vs chunk retrieval)
- **Better extraction** with format rules and few-shot examples
- **Centralized prompts** in `llm/prompts.py` for easy review, maintenance, and consistency across LLM clients

## Files to Create/Modify

**New Files**:

- `api/services/metadata_service.py`
- `api/services/query_service.py`
- `llm/prompts.py`
- `scripts/test_metadata_retrieval.py`

**Modified Files**:

- `api/services/answer_service.py` (major refactor)
- `llm/ollama_client.py` (prompt rewrite to use centralized prompts)
- `llm/openai_client.py` (update to use centralized prompts, remove duplicate code)
- `ingest/indexer_qdrant.py` (contextual embeddings)
- `ingest/indexer_opensearch.py` (metadata in index, contextual text)
- `ingest/worker.py` (generate embeddings from contextual text)
- `api/services/rerank.py` (enhanced reranking)
- `scripts/rag_test_suite.py` (metadata tests, cross-doc tests, 95% validation)

### To-dos

- [x] Simplify answer_service.py to use single hybrid query instead of two-query approach (Both approaches kept and configurable via RAG_STRATEGY env var)
- [x] Make hybrid search weights configurable via environment variables (BM25/vector) (HYBRID_BM25_WEIGHT and HYBRID_VECTOR_WEIGHT implemented)
- [x] Increase max_context_chunks default and add dynamic calculation based on context window (Default set to 30, uses OLLAMA_CONTEXT_LENGTH)
- [x] Update context truncation in ollama_client.py to use full available context window (Uses 75% of OLLAMA_CONTEXT_LENGTH dynamically)
- [x] Create rag_test_suite.py script for repeatable testing with database storage (Script created with metadata-first and cross-doc validation)
- [x] Add auto-generation of test questions in worker.py after document ingestion (Auto-generation implemented in worker.py)
- [x] Create compare_test_runs.py script for comparing test results over time (Script created)
- [x] Create benchmark_rag_configs.py to test different hybrid search configurations (Script created)