"""
Upload router
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List
import os
import tempfile
import uuid
from api.models.responses import UploadResponse
from api.db import get_db_session
from api.db.schema import Document, DocumentStatus
from api.services.storage_service import storage_service
from ingest.worker import worker

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=List[UploadResponse])
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """
    Upload and ingest one or more documents
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    allowed_extensions = ['.pdf', '.docx']
    results = []

    for file in files:
        try:
            # Validate file type
            if not file.filename:
                results.append(UploadResponse(
                    document_id="",
                    filename="",
                    status="failed",
                    message="Filename required"
                ))
                continue

            file_ext = os.path.splitext(file.filename)[1].lower()

            if file_ext not in allowed_extensions:
                results.append(UploadResponse(
                    document_id="",
                    filename=file.filename,
                    status="failed",
                    message=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
                ))
                continue

            # Create document record
            document_id = str(uuid.uuid4())
            db = get_db_session()
            try:
                doc = Document(
                    id=document_id,
                    filename=file.filename,
                    status=DocumentStatus.UPLOADED,
                    s3_path=None,
                    metadata_json={}
                )
                db.add(doc)
                db.commit()
            finally:
                db.close()

            # Save file temporarily and upload to storage immediately
            temp_file = None
            try:
                # Create temp file
                suffix = file_ext
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    content = await file.read()
                    tmp.write(content)
                    temp_file = tmp.name

                # Upload to storage immediately so file is available for viewing
                try:
                    with open(temp_file, 'rb') as f:
                        file_data = f.read()

                    s3_path = storage_service.upload_file(
                        bucket="nda-raw",
                        object_name=f"{document_id}/{file.filename}",
                        file_data=file_data,
                        content_type="application/pdf" if file_ext == '.pdf' else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

                    # Update document with s3_path
                    db = get_db_session()
                    try:
                        doc = db.query(Document).filter(Document.id == document_id).first()
                        if doc:
                            doc.s3_path = s3_path
                            db.commit()
                    finally:
                        db.close()
                except Exception as e:
                    print(f"Warning: Failed to upload file to storage: {e}")

                # Queue ingestion in background
                background_tasks.add_task(
                    ingest_document_background,
                    document_id,
                    temp_file,
                    file.filename
                )

                results.append(UploadResponse(
                    document_id=document_id,
                    filename=file.filename,
                    status="uploaded",
                    message="File uploaded. Processing in background."
                ))
            except Exception as e:
                # Clean up temp file on error
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)

                # Update document status to failed
                db = get_db_session()
                try:
                    doc = db.query(Document).filter(Document.id == document_id).first()
                    if doc:
                        doc.status = DocumentStatus.FAILED
                        db.commit()
                finally:
                    db.close()

                results.append(UploadResponse(
                    document_id=document_id,
                    filename=file.filename,
                    status="failed",
                    message=f"Upload failed: {str(e)}"
                ))
        except Exception as e:
            results.append(UploadResponse(
                document_id="",
                filename=file.filename if file.filename else "unknown",
                status="failed",
                message=f"Upload failed: {str(e)}"
            ))

    return results


@router.post("/single", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload and ingest a single document (legacy endpoint for backward compatibility)
    """
    # Use the batch upload endpoint
    results = await upload_files(background_tasks, [file])
    if results and len(results) > 0:
        return results[0]
    else:
        raise HTTPException(status_code=500, detail="Upload failed")


def ingest_document_background(document_id: str, file_path: str, filename: str):
    """Background task for document ingestion"""
    try:
        worker.ingest_document(file_path, filename, document_id)
    except Exception as e:
        print(f"Background ingestion failed for {filename}: {e}")
    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            os.remove(file_path)
