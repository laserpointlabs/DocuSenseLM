"""
Admin router
"""
from fastapi import APIRouter, HTTPException
from api.models.responses import StatsResponse
from api.services.db_service import db_service
from api.db import get_db_session
from ingest.indexer_opensearch import opensearch_indexer
from ingest.indexer_qdrant import qdrant_indexer
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
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


@router.post("/reindex/{document_id}")
async def reindex_document(document_id: str):
    """
    Re-index a document by re-running ingestion
    """
    from ingest.worker import worker
    from api.db.schema import Document, DocumentStatus
    from api.services.storage_service import storage_service
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

            file_data = storage_service.download_file(bucket, object_name)

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


@router.post("/reindex/all")
async def reindex_all():
    """
    Re-index all documents
    """
    # TODO: Implement full re-indexing
    return {"message": "Re-indexing all documents", "status": "pending"}
