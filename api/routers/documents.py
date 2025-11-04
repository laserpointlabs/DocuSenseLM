"""
Documents router
"""
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from typing import Optional
from api.models.responses import DocumentResponse, DocumentListResponse
from api.services.db_service import db_service
from api.services.storage_service import storage_service
from api.db import get_db_session
from io import BytesIO

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get document by ID with full metadata and parties
    """
    db = get_db_session()
    try:
        doc = db_service.get_document(db, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get document metadata
        doc_metadata = db_service.get_document_metadata(db, document_id)

        # Get parties
        parties = db_service.get_parties(db, document_id)

        # Build comprehensive metadata
        metadata = doc.metadata_json or {}
        if doc_metadata:
            metadata.update({
                'effective_date': doc_metadata.effective_date.isoformat() if doc_metadata.effective_date else None,
                'governing_law': doc_metadata.governing_law,  # This will be in metadata
                'is_mutual': doc_metadata.is_mutual,
                'term_months': doc_metadata.term_months,
                'survival_months': doc_metadata.survival_months,
            })

        # Ensure governing_law is at top level for easy access
        if not metadata.get('governing_law') and doc_metadata and doc_metadata.governing_law:
            metadata['governing_law'] = doc_metadata.governing_law

        metadata['parties'] = [
            {
                'name': p.party_name,
                'type': p.party_type,
                'address': p.address
            }
            for p in parties
        ]

        return DocumentResponse(
            id=str(doc.id),
            filename=doc.filename,
            upload_date=doc.upload_date,
            status=doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
            metadata=metadata
        )
    finally:
        db.close()


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    List documents with pagination
    """
    db = get_db_session()
    try:
        documents, total = db_service.list_documents(db, skip=skip, limit=limit)

        doc_responses = [
            DocumentResponse(
                id=str(doc.id),
                filename=doc.filename,
                upload_date=doc.upload_date,
                status=doc.status.value if hasattr(doc.status, 'value') else str(doc.status),
                metadata=doc.metadata_json
            )
            for doc in documents
        ]

        return DocumentListResponse(
            documents=doc_responses,
            total=total
        )
    finally:
        db.close()


@router.get("/{document_id}/file")
async def get_document_file(document_id: str):
    """
    Get document file (PDF/DOCX) for viewing
    """
    db = get_db_session()
    try:
        doc = db_service.get_document(db, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Extract bucket and object name from s3_path
        # Format: bucket_name/object_name
        # For now, assume bucket is "nda-raw" and object is in format "{document_id}/{filename}"
        # If s3_path is not set, construct it from document_id and filename
        if doc.s3_path:
            # Parse s3_path if it exists
            if '/' in doc.s3_path:
                parts = doc.s3_path.split('/', 1)
                bucket = parts[0] if parts[0] else "nda-raw"
                object_name = parts[1] if len(parts) > 1 else f"{document_id}/{doc.filename}"
            else:
                bucket = "nda-raw"
                object_name = f"{document_id}/{doc.filename}"
        else:
            # Construct path from document_id and filename
            bucket = "nda-raw"
            object_name = f"{str(doc.id)}/{doc.filename}"

        try:
            file_data = storage_service.download_file("nda-raw", object_name)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve file: {str(e)}")

        # Determine content type
        if doc.filename.lower().endswith('.pdf'):
            content_type = "application/pdf"
        elif doc.filename.lower().endswith('.docx'):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            content_type = "application/octet-stream"

        return Response(
            content=file_data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{doc.filename}"',
                "Access-Control-Allow-Origin": "*",
            }
        )
    finally:
        db.close()


@router.get("/{document_id}/chunks")
async def get_document_chunks(document_id: str):
    """
    Get all chunks/clauses for a document
    """
    db = get_db_session()
    try:
        doc = db_service.get_document(db, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        chunks = db_service.get_document_chunks(db, document_id)

        chunk_list = [
            {
                "id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "section_type": chunk.section_type,
                "clause_number": chunk.clause_number,
                "clause_title": chunk.clause_title,  # Include clause title
                "text": chunk.text,
                "page_num": chunk.page_num,
                "span_start": chunk.span_start,
                "span_end": chunk.span_end,
            }
            for chunk in chunks
        ]

        return {"chunks": chunk_list}
    finally:
        db.close()


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document and all associated data
    """
    from ingest.indexer_opensearch import opensearch_indexer
    from ingest.indexer_qdrant import qdrant_indexer
    from api.db.schema import Document, DocumentChunk, Party, DocumentMetadata

    db = get_db_session()
    try:
        doc = db_service.get_document(db, document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        filename = doc.filename

        # Delete from search indices using the indexer methods
        # CRITICAL: Delete from indices BEFORE database to ensure we have the document_id
        opensearch_deleted = 0
        qdrant_deleted = 0

        try:
            # Delete from OpenSearch
            try:
                opensearch_deleted = opensearch_indexer.delete_document(document_id)
                print(f"Deleted {opensearch_deleted} chunks from OpenSearch for document {document_id}")
            except Exception as e:
                print(f"ERROR: Failed to delete from OpenSearch: {e}")
                # Don't fail the entire deletion, but log the error

            # Delete from Qdrant
            try:
                qdrant_deleted = qdrant_indexer.delete_document(document_id)
                print(f"Deleted {qdrant_deleted} points from Qdrant for document {document_id}")
            except Exception as e:
                print(f"ERROR: Failed to delete from Qdrant: {e}")
                # Don't fail the entire deletion, but log the error

        except Exception as e:
            print(f"ERROR: Error deleting from search indices: {e}")

        # Verify deletion if possible (optional, but helpful for debugging)
        try:
            # Quick verification - check if any chunks remain in OpenSearch
            verify_result = opensearch_indexer.client.search(
                index=opensearch_indexer.index_name,
                body={
                    "query": {"term": {"doc_id": document_id}},
                    "size": 0
                }
            )
            remaining = verify_result["hits"]["total"]["value"]
            if remaining > 0:
                print(f"WARNING: {remaining} chunks still remain in OpenSearch after deletion attempt")
        except Exception as e:
            print(f"Warning: Could not verify OpenSearch deletion: {e}")

        try:
            # Quick verification - check if any points remain in Qdrant
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            verify_filter = Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=document_id)
                    )
                ]
            )
            verify_results = qdrant_indexer.client.scroll(
                collection_name=qdrant_indexer.collection_name,
                scroll_filter=verify_filter,
                limit=1
            )
            remaining = len(verify_results[0])
            if remaining > 0:
                print(f"WARNING: {remaining} points still remain in Qdrant after deletion attempt")
        except Exception as e:
            print(f"Warning: Could not verify Qdrant deletion: {e}")

        # Delete from storage (raw file)
        if doc.s3_path:
            try:
                if '/' in doc.s3_path:
                    parts = doc.s3_path.split('/', 1)
                    bucket = parts[0] if parts[0] else "nda-raw"
                    object_name = parts[1] if len(parts) > 1 else f"{document_id}/{filename}"
                else:
                    bucket = "nda-raw"
                    object_name = f"{document_id}/{filename}"

                storage_service.delete_file(bucket, object_name)
            except Exception as e:
                print(f"Warning: Failed to delete file from storage: {e}")

        # Delete processed file from storage
        try:
            storage_service.delete_file("nda-processed", f"{document_id}/nda_record.json")
        except Exception as e:
            # Processed file might not exist, that's okay
            pass

        # Delete from database - delete related records first due to foreign key constraints
        # Delete chunks
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        # Delete parties
        db.query(Party).filter(Party.document_id == document_id).delete()
        # Delete metadata
        db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).delete()
        # Finally delete the document
        db.delete(doc)
        db.commit()

        return {
            "message": f"Document {filename} deleted successfully",
            "document_id": document_id,
            "deletion_stats": {
                "opensearch_chunks_deleted": opensearch_deleted,
                "qdrant_points_deleted": qdrant_deleted,
                "database_records_deleted": True
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
    finally:
        db.close()
