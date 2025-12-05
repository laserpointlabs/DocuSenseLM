"""
Admin router
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from api.models.responses import StatsResponse
from api.services.db_service import db_service
from api.db import get_db_session
from api.db.schema import User
from api.middleware.auth import get_current_user, get_current_admin_user
from ingest.indexer_opensearch import opensearch_indexer
from ingest.indexer_qdrant import qdrant_indexer
from datetime import datetime
import threading

router = APIRouter(prefix="/admin", tags=["admin"])

# In-memory progress tracking for reindexing
_reindex_progress = {
    "is_running": False,
    "total": 0,
    "completed": 0,
    "current": None,
    "errors": 0
}
_progress_lock = threading.Lock()


@router.get("/reindex/progress")
async def get_reindex_progress(current_user: User = Depends(get_current_admin_user)):
    """Get current reindexing progress"""
    import logging
    logger = logging.getLogger(__name__)
    
    with _progress_lock:
        progress = {
            "is_running": _reindex_progress["is_running"],
            "total": _reindex_progress["total"],
            "completed": _reindex_progress["completed"],
            "current": _reindex_progress["current"],
            "errors": _reindex_progress["errors"],
            "progress_percent": int((_reindex_progress["completed"] / _reindex_progress["total"] * 100)) if _reindex_progress["total"] > 0 else 0
        }
        
        # Log progress for debugging
        if progress["is_running"]:
            logger.info(f"📊 Progress API called: {progress['completed']}/{progress['total']} ({progress['progress_percent']}%) - Current: {progress['current']}")
        
        return progress


@router.get("/stats", response_model=StatsResponse)
async def get_stats(current_user: User = Depends(get_current_admin_user)):
    """
    Get system statistics
    """
    db = get_db_session()
    try:
        stats = db_service.get_stats(db)

        # Check service status
        opensearch_status = "unknown"
        qdrant_status = "unknown"

        try:
            opensearch_indexer.client.cluster.health()
            opensearch_status = "healthy"
        except:
            opensearch_status = "unhealthy"

        try:
            qdrant_indexer.client.get_collections()
            qdrant_status = "healthy"
        except:
            qdrant_status = "unhealthy"

        return StatsResponse(
            total_documents=stats['total_documents'],
            total_chunks=stats['total_chunks'],
            total_questions=stats['total_questions'],
            indexed_documents=stats['indexed_documents'],
            opensearch_status=opensearch_status,
            qdrant_status=qdrant_status
        )
    finally:
        db.close()


def _do_reindex_all():
    """Background task to reindex all documents"""
    import uuid
    from api.db.schema import Document, DocumentChunk, DocumentStatus
    from ingest.indexer_opensearch import opensearch_indexer
    from ingest.indexer_qdrant import qdrant_indexer
    from ingest.embedder import get_embedder
    import logging
    import time
    
    logger = logging.getLogger(__name__)
    
    db = get_db_session()
    try:
        documents = db.query(Document).filter(
            Document.status == DocumentStatus.PROCESSED
        ).all()
        
        if not documents:
            with _progress_lock:
                _reindex_progress["is_running"] = False
            logger.info("No processed documents found to re-index")
            return
        
        # Initialize progress tracking
        with _progress_lock:
            _reindex_progress["is_running"] = True
            _reindex_progress["total"] = len(documents)
            _reindex_progress["completed"] = 0
            _reindex_progress["current"] = None
            _reindex_progress["errors"] = 0
        logger.info(f"Starting reindex of {len(documents)} documents")
        
        # STEP 1: Set ALL documents to PROCESSING status BEFORE starting reindexing
        logger.info(f"Setting {len(documents)} documents to PROCESSING status")
        
        # Use a fresh session to set status - ensures it's committed and visible
        status_db = get_db_session()
        try:
            doc_ids = [str(doc.id) for doc in documents]
            for doc_id in doc_ids:
                doc_uuid = uuid.UUID(doc_id)
                fresh_doc = status_db.query(Document).filter(Document.id == doc_uuid).first()
                if fresh_doc:
                    fresh_doc.status = DocumentStatus.PROCESSING
                    logger.debug(f"Set {doc_id} to PROCESSING")
            status_db.flush()  # Flush before commit
            status_db.commit()
            logger.info(f"✓ All {len(documents)} documents set to PROCESSING status and committed")
            
            # Verify status was set by querying again
            verify_db = get_db_session()
            try:
                for doc_id in doc_ids[:3]:  # Check first 3
                    doc_uuid = uuid.UUID(doc_id)
                    verify_doc = verify_db.query(Document).filter(Document.id == doc_uuid).first()
                    if verify_doc:
                        logger.info(f"Verified {doc_id} status is {verify_doc.status.value}")
            finally:
                verify_db.close()
        finally:
            status_db.close()
        
        # Small delay to ensure UI sees the status change before reindexing starts
        import time
        time.sleep(0.5)
        
        def _reindex_document(doc_id: str, filename: str):
            """Helper function to reindex a single document - status is already PROCESSING"""
            import logging
            logger = logging.getLogger(__name__)
            
            doc_db = get_db_session()
            try:
                # Convert doc_id string to UUID for querying
                doc_uuid = uuid.UUID(doc_id)
                
                # Get document - status should already be PROCESSING from caller
                doc = doc_db.query(Document).filter(Document.id == doc_uuid).first()
                if not doc:
                    logger.warning(f"Document {doc_id} not found for reindexing")
                    return False
                
                logger.info(f"Reindexing document {doc_id} ({filename}) - status should be PROCESSING")
                
                # Get chunks
                chunks = doc_db.query(DocumentChunk).filter(
                    DocumentChunk.document_id == doc_uuid
                ).order_by(DocumentChunk.chunk_index).all()
                
                if not chunks:
                    # No chunks found, set back to PROCESSED
                    doc.status = DocumentStatus.PROCESSED
                    doc_db.commit()
                    doc_db.refresh(doc)
                    return False
                
                # Get document metadata (these functions accept string IDs)
                metadata = db_service.get_document_metadata(doc_db, doc_id)
                parties = db_service.get_parties(doc_db, doc_id)
                
                metadata_dict = {
                    'parties': [p.party_name for p in parties],
                    'effective_date': metadata.effective_date.isoformat() if metadata and metadata.effective_date else None,
                    'governing_law': metadata.governing_law if metadata else None,
                    'is_mutual': metadata.is_mutual if metadata else None,
                    'term_months': metadata.term_months if metadata else None,
                    'survival_months': metadata.survival_months if metadata else None,
                }
                
                # Prepare chunks
                chunk_dicts = []
                chunk_texts = []
                
                for chunk in chunks:
                    chunk_dicts.append({
                        'id': str(chunk.id),
                        'chunk_id': str(chunk.id),
                        'document_id': doc_id,
                        'text': chunk.text,
                        'section_type': chunk.section_type,
                        'clause_number': chunk.clause_number,
                        'page_num': chunk.page_num,
                        'span_start': chunk.span_start,
                        'span_end': chunk.span_end,
                        'source_uri': doc.s3_path or '',
                    })
                    chunk_texts.append(chunk.text)
                
                # Generate embeddings
                embedder = get_embedder()
                embeddings = embedder.embed_batch(chunk_texts)
                
                # Delete existing indices (these accept string IDs)
                opensearch_indexer.delete_document(doc_id)
                qdrant_indexer.delete_document(doc_id)
                
                # Re-index (status stays as PROCESSING during this time)
                opensearch_indexer.index_chunks(chunk_dicts, metadata_dict)
                qdrant_indexer.index_chunks(chunk_dicts, embeddings)
                
                # Status stays PROCESSING during entire reindex - now set it back to PROCESSED
                # Use a fresh session to ensure the change is visible
                final_db = get_db_session()
                try:
                    final_doc = final_db.query(Document).filter(Document.id == doc_uuid).first()
                    if final_doc:
                        final_doc.status = DocumentStatus.PROCESSED
                        final_db.commit()
                        logger.info(f"✓ Document {doc_id} reindex complete - status set to PROCESSED")
                finally:
                    final_db.close()
                
                return True
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error re-indexing document {doc_id}: {e}")
                # Set status to FAILED on error
                try:
                    doc_uuid = uuid.UUID(doc_id)
                    doc = doc_db.query(Document).filter(Document.id == doc_uuid).first()
                    if doc:
                        doc.status = DocumentStatus.FAILED
                        doc_db.commit()
                        doc_db.refresh(doc)
                except Exception as e2:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to update status to FAILED for {doc_id}: {e2}")
                return False
            finally:
                doc_db.close()
        
        # Re-index all documents sequentially
        # IMPORTANT: Process one at a time so status updates are visible in real-time
        success_count = 0
        error_count = 0
        
        import logging
        logger = logging.getLogger(__name__)
        
        # STEP 2: Now reindex each document
        for idx, doc in enumerate(documents, 1):
            try:
                # Update progress - currently processing this document
                with _progress_lock:
                    _reindex_progress["current"] = doc.filename
                    _reindex_progress["completed"] = idx - 1
                    logger.info(f"📝 Progress updated: current={doc.filename}, completed={idx-1}/{len(documents)}")
                
                logger.info(f"[{idx}/{len(documents)}] Reindexing {doc.filename}")
                
                # Reindex
                if _reindex_document(str(doc.id), doc.filename):
                    success_count += 1
                    logger.info(f"[{idx}/{len(documents)}] Completed reindex for {doc.filename}")
                else:
                    error_count += 1
                    logger.warning(f"[{idx}/{len(documents)}] Failed reindex for {doc.filename}")
                
                # Update progress - document completed
                with _progress_lock:
                    _reindex_progress["completed"] = idx
                    _reindex_progress["errors"] = error_count
                    logger.info(f"✅ Progress updated: completed={idx}/{len(documents)}, errors={error_count}")
                    
            except Exception as e:
                logger.error(f"Error re-indexing document {doc.id}: {e}")
                # Ensure status is updated even if exception occurs
                try:
                    doc_db = get_db_session()
                    doc_obj = doc_db.query(Document).filter(Document.id == doc.id).first()
                    if doc_obj:
                        if doc_obj.status == DocumentStatus.PROCESSING:
                            doc_obj.status = DocumentStatus.FAILED
                            doc_db.commit()
                            doc_db.refresh(doc_obj)
                            logger.info(f"Document {doc.id} status set to FAILED due to error")
                    doc_db.close()
                except Exception as e2:
                    logger.error(f"Failed to update status to FAILED for {doc.id}: {e2}")
                error_count += 1
        
        # Clear progress tracking
        with _progress_lock:
            _reindex_progress["is_running"] = False
            _reindex_progress["current"] = None
        
        logger.info(f"✅ Re-indexing completed: {success_count} success, {error_count} errors")
    except Exception as e:
        # Clear progress on error
        logger.error(f"❌ Re-indexing failed with error: {e}")
        with _progress_lock:
            _reindex_progress["is_running"] = False
            _reindex_progress["current"] = None
    finally:
        db.close()


@router.post("/reindex/all")
async def reindex_all(background_tasks: BackgroundTasks, current_user: User = Depends(get_current_admin_user)):
    """
    Start re-indexing all processed documents in the background
    """
    from api.db.schema import Document, DocumentStatus
    
    # Check if reindex is already running
    with _progress_lock:
        if _reindex_progress["is_running"]:
            return {
                "message": "Re-indexing is already in progress",
                "status": "already_running"
            }
    
    # Check if there are documents to reindex
    db = get_db_session()
    try:
        doc_count = db.query(Document).filter(
            Document.status == DocumentStatus.PROCESSED
        ).count()
        
        if doc_count == 0:
            return {
                "message": "No processed documents found to re-index",
                "status": "success",
                "total": 0
            }
    finally:
        db.close()
    
    # Start background task
    background_tasks.add_task(_do_reindex_all)
    
    return {
        "message": f"Re-indexing started for {doc_count} documents",
        "status": "started",
        "total": doc_count
    }


@router.post("/reindex/{document_id}")
async def reindex_document(document_id: str, current_user: User = Depends(get_current_admin_user)):
    """
    Re-index a document by re-running ingestion
    """
    from ingest.worker import worker
    from api.db.schema import Document, DocumentStatus
    from api.services.service_registry import get_storage_service
    import tempfile
    import os

    db = get_db_session()
    try:
        doc = db_service.get_document(db, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if not doc.s3_path:
            raise HTTPException(status_code=400, detail="Document file not found in storage")

        # Download file from storage
        try:
            # Parse s3_path
            if '/' in doc.s3_path:
                parts = doc.s3_path.split('/', 1)
                bucket = parts[0] if parts[0] else "nda-raw"
                object_name = parts[1] if len(parts) > 1 else f"{document_id}/{doc.filename}"
            else:
                bucket = "nda-raw"
                object_name = f"{document_id}/{doc.filename}"

            storage = get_storage_service()
            file_data = storage.download_file(bucket, object_name)

            # Save to temp file
            suffix = os.path.splitext(doc.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_data)
                temp_file = tmp.name

            # Update status to processing
            doc.status = DocumentStatus.PROCESSING
            db.commit()

            # Run ingestion in background (using background tasks would be better, but this works)
            try:
                worker.ingest_document(temp_file, doc.filename, document_id)
                return {"message": f"Re-indexing completed for document {document_id}", "status": "success"}
            except Exception as e:
                doc.status = DocumentStatus.FAILED
                db.commit()
                return {"message": f"Re-indexing failed: {str(e)}", "status": "failed"}
            finally:
                # Clean up temp file
                if os.path.exists(temp_file):
                    os.remove(temp_file)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to re-index: {str(e)}")
    finally:
        db.close()
