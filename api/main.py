"""
FastAPI main application
"""
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from api.routers import (
    search, answer, upload, documents, admin, health, competency, registry, auth,
    templates, workflow
)
from api.services.bootstrap import configure_services_from_env
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def check_and_reindex_if_needed():
    """
    Check if search indexes are empty but documents exist in database.
    If so, optionally auto-reindex based on AUTO_REINDEX_ON_STARTUP env var.
    """
    import os
    
    auto_reindex = os.getenv("AUTO_REINDEX_ON_STARTUP", "false").lower() == "true"
    if not auto_reindex:
        logger.info("AUTO_REINDEX_ON_STARTUP is disabled, skipping index check")
        return
    
    try:
        from api.db import get_db_session
        from api.db.schema import Document, DocumentStatus
        from ingest.indexer_opensearch import opensearch_indexer
        from ingest.indexer_qdrant import qdrant_indexer
        
        # Check database for documents
        db = get_db_session()
        try:
            doc_count = db.query(Document).filter(
                Document.status == DocumentStatus.PROCESSED
            ).count()
            
            if doc_count == 0:
                logger.info("No processed documents in database, skipping reindex check")
                return
            
            # Check OpenSearch index count
            try:
                opensearch_count = opensearch_indexer.client.count(
                    index=opensearch_indexer.index_name
                )["count"]
            except Exception as e:
                logger.warning(f"Could not check OpenSearch count: {e}")
                opensearch_count = 0
            
            # Check Qdrant collection count
            try:
                qdrant_collection = qdrant_indexer.client.get_collection(
                    qdrant_indexer.collection_name
                )
                qdrant_count = qdrant_collection.points_count
            except Exception as e:
                logger.warning(f"Could not check Qdrant count: {e}")
                qdrant_count = 0
            
            logger.info(
                f"Index status check: {doc_count} documents in DB, "
                f"{opensearch_count} in OpenSearch, {qdrant_count} in Qdrant"
            )
            
            # If indexes are empty but documents exist, trigger reindex
            if doc_count > 0 and (opensearch_count == 0 or qdrant_count == 0):
                logger.warning(
                    f"⚠️  Search indexes appear empty ({opensearch_count} OpenSearch, "
                    f"{qdrant_count} Qdrant) but {doc_count} documents exist in database. "
                    "Auto-reindexing..."
                )
                
                # Import reindex logic (use the actual reindex function from admin router)
                from api.db.schema import DocumentChunk
                from api.services.db_service import db_service
                from ingest.embedder import get_embedder
                
                # Run reindex synchronously but log that it's happening
                # This will take some time but ensures indexes are populated before serving requests
                logger.info("Starting synchronous reindex to populate empty indexes...")
                try:
                    # Use the same logic as reindex_all endpoint
                    success_count = 0
                    error_count = 0
                    
                    for doc in db.query(Document).filter(Document.status == DocumentStatus.PROCESSED).all():
                        try:
                            chunks = db.query(DocumentChunk).filter(
                                DocumentChunk.document_id == doc.id
                            ).order_by(DocumentChunk.chunk_index).all()
                            
                            if not chunks:
                                continue
                            
                            metadata = db_service.get_document_metadata(db, str(doc.id))
                            parties = db_service.get_parties(db, str(doc.id))
                            
                            metadata_dict = {
                                'parties': [p.party_name for p in parties],
                                'effective_date': metadata.effective_date.isoformat() if metadata and metadata.effective_date else None,
                                'governing_law': metadata.governing_law if metadata else None,
                                'is_mutual': metadata.is_mutual if metadata else None,
                                'term_months': metadata.term_months if metadata else None,
                                'survival_months': metadata.survival_months if metadata else None,
                            }
                            
                            chunk_dicts = []
                            chunk_texts = []
                            
                            for chunk in chunks:
                                chunk_dicts.append({
                                    'id': str(chunk.id),
                                    'chunk_id': str(chunk.id),
                                    'document_id': str(doc.id),
                                    'text': chunk.text,
                                    'section_type': chunk.section_type,
                                    'clause_number': chunk.clause_number,
                                    'page_num': chunk.page_num,
                                    'span_start': chunk.span_start,
                                    'span_end': chunk.span_end,
                                    'source_uri': doc.s3_path or '',
                                })
                                chunk_texts.append(chunk.text)
                            
                            embedder = get_embedder()
                            embeddings = embedder.embed_batch(chunk_texts)
                            
                            opensearch_indexer.delete_document(str(doc.id))
                            qdrant_indexer.delete_document(str(doc.id))
                            
                            opensearch_indexer.index_chunks(chunk_dicts, metadata_dict)
                            qdrant_indexer.index_chunks(chunk_dicts, embeddings)
                            
                            success_count += 1
                        except Exception as e:
                            logger.error(f"Error re-indexing document {doc.id}: {e}")
                            error_count += 1
                    
                    logger.info(
                        f"✅ Auto-reindex completed: {success_count} success, {error_count} errors"
                    )
                except Exception as e:
                    logger.error(f"❌ Auto-reindex failed: {e}")
            else:
                logger.info("✅ Search indexes are populated, no reindex needed")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.warning(f"Could not check index status: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("NDA Dashboard API starting up...")
    
    # Configure service overrides based on environment
    configure_services_from_env()
    
    # Check and optionally reindex if indexes are empty
    check_and_reindex_if_needed()
    
    yield
    
    # Shutdown (if needed)
    logger.info("NDA Dashboard API shutting down...")

app = FastAPI(
    title="NDA Dashboard API",
    description="API for NDA document search and analysis",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - must be added before exception handlers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Exception handlers to ensure CORS headers are added even on errors
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers={"Access-Control-Allow-Origin": "*"},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Log the validation errors for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Validation error: {exc.errors()}")
    logger.error(f"Request path: {request.url.path}")
    logger.error(f"Request method: {request.method}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
        headers={"Access-Control-Allow-Origin": "*"},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(answer.router)
app.include_router(upload.router)
app.include_router(documents.router)
app.include_router(admin.router)
app.include_router(competency.router)
app.include_router(registry.router)
app.include_router(templates.router)
app.include_router(workflow.router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "NDA Dashboard API",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
