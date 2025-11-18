"""
Upload router
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from typing import List
import os
import tempfile
import uuid
import logging
from api.models.responses import UploadResponse
from api.db import get_db_session
from api.db.schema import Document, DocumentStatus, User
from api.middleware.auth import get_current_user
from api.services.service_registry import get_storage_service
from ingest.worker import worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=List[UploadResponse])
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload and ingest one or more documents
    
    Only PDF files are accepted. DOCX files will be rejected.
    For NDA creation, use the workflow endpoint which automatically converts templates to PDF.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    allowed_extensions = ['.pdf']
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

            # Reject DOCX files - only PDFs are allowed
            if file_ext == '.docx':
                results.append(UploadResponse(
                    document_id="",
                    filename=file.filename,
                    status="failed",
                    message="DOCX files are not accepted. Please convert to PDF before uploading. For NDA creation, use the workflow endpoint which automatically generates PDFs."
                ))
                continue

            if file_ext not in allowed_extensions:
                results.append(UploadResponse(
                    document_id="",
                    filename=file.filename,
                    status="failed",
                    message=f"Only PDF files are accepted. File type '{file_ext}' is not supported."
                ))
                continue
            
            # Verify file is actually a PDF by checking magic bytes
            content = await file.read()
            await file.seek(0)  # Reset file pointer
            
            if not content.startswith(b'%PDF'):
                results.append(UploadResponse(
                    document_id="",
                    filename=file.filename,
                    status="failed",
                    message="File does not appear to be a valid PDF. Please ensure the file is a PDF document."
                ))
                continue

            # Create document record and mark as processing immediately
            document_id = str(uuid.uuid4())
            
            # Ensure filename ends with .pdf
            pdf_filename = file.filename
            if not pdf_filename.lower().endswith('.pdf'):
                pdf_filename = os.path.splitext(pdf_filename)[0] + '.pdf'
            
            db = get_db_session()
            try:
                doc = Document(
                    id=document_id,
                    filename=pdf_filename,
                    status=DocumentStatus.PROCESSING,
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
                # Create temp file (always PDF now)
                suffix = '.pdf'
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    content = await file.read()
                    tmp.write(content)
                    temp_file = tmp.name

                # Upload to storage immediately so file is available for viewing
                try:
                    with open(temp_file, 'rb') as f:
                        file_data = f.read()

                    # Ensure filename ends with .pdf
                    pdf_filename = file.filename
                    if not pdf_filename.lower().endswith('.pdf'):
                        pdf_filename = os.path.splitext(pdf_filename)[0] + '.pdf'

                    storage = get_storage_service()
                    s3_path = storage.upload_file(
                        bucket="nda-raw",
                        object_name=f"{document_id}/{pdf_filename}",
                        file_data=file_data,
                        content_type="application/pdf"
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
                    filename=pdf_filename,
                    status="uploaded",
                    message="PDF file uploaded. Processing in background."
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
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
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
