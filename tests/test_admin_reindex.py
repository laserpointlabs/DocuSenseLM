"""
Tests for admin reindex endpoints
"""
import uuid
from pathlib import Path
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import admin as admin_router
from api.db import get_db_session
from api.db.schema import Document, DocumentChunk, DocumentStatus
from api.services.db_service import db_service


def create_dummy_pdf(tmp_path: Path, filename: str = "test.pdf") -> Path:
    """
    Create a minimal valid PDF file for testing.
    Uses a simple PDF structure that PDF parsers can handle.
    """
    pdf_path = tmp_path / filename
    
    # Create a minimal PDF file (PDF 1.4 format)
    # This is a very basic PDF structure that should work with most PDF parsers
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Document) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000317 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
400
%%EOF"""
    
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def client():
    """Create a test FastAPI client with admin router"""
    test_app = FastAPI()
    test_app.include_router(admin_router.router)
    return TestClient(test_app)


@pytest.fixture
def sample_document(fake_service_registry):
    """Create a sample processed document in the database"""
    db = get_db_session()
    try:
        doc_id = uuid.uuid4()
        document = Document(
            id=doc_id,
            filename="test_nda.pdf",
            status=DocumentStatus.PROCESSED,
            s3_path="nda-raw/test_nda.pdf",
            upload_date=datetime.now(),
        )
        db.add(document)
        
        # Create some chunks for the document
        for i in range(3):
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc_id,
                chunk_index=i,
                chunk_text=f"Chunk {i} text content for testing reindex functionality.",
                metadata_json={"page_num": i + 1},
            )
            db.add(chunk)
        
        db.commit()
        return str(doc_id)
    finally:
        db.close()


@pytest.fixture
def multiple_documents(fake_service_registry):
    """Create multiple processed documents for testing bulk reindex"""
    db = get_db_session()
    try:
        doc_ids = []
        for i in range(3):
            doc_id = uuid.uuid4()
            document = Document(
                id=doc_id,
                filename=f"test_nda_{i}.pdf",
                status=DocumentStatus.PROCESSED,
                s3_path=f"nda-raw/test_nda_{i}.pdf",
                upload_date=datetime.now(),
            )
            db.add(document)
            
            # Create chunks
            for j in range(2):
                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc_id,
                    chunk_index=j,
                    chunk_text=f"Document {i}, Chunk {j} content.",
                    metadata_json={"page_num": j + 1},
                )
                db.add(chunk)
            
            doc_ids.append(str(doc_id))
        
        db.commit()
        return doc_ids
    finally:
        db.close()


def test_get_reindex_progress_no_reindex(client):
    """Test getting reindex progress when no reindex is running"""
    response = client.get("/admin/reindex/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["is_running"] is False
    assert data["total"] == 0
    assert data["completed"] == 0
    assert data["errors"] == 0
    assert data["progress_percent"] == 0


def test_reindex_all_no_documents(client):
    """Test reindex all when there are no processed documents"""
    response = client.post("/admin/reindex/all")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total"] == 0
    assert "No processed documents" in data["message"]


def test_reindex_all_with_documents(client, multiple_documents, monkeypatch):
    """Test reindex all endpoint with existing documents"""
    # Mock the indexers to avoid needing external services
    def mock_index_document(*args, **kwargs):
        return True
    
    def mock_index_chunks(*args, **kwargs):
        return True
    
    monkeypatch.setattr("ingest.indexer_opensearch.opensearch_indexer.index_document", mock_index_document)
    monkeypatch.setattr("ingest.indexer_qdrant.qdrant_indexer.index_document", mock_index_document)
    monkeypatch.setattr("ingest.indexer_opensearch.opensearch_indexer.index_chunks", mock_index_chunks)
    monkeypatch.setattr("ingest.indexer_qdrant.qdrant_indexer.index_chunks", mock_index_chunks)
    
    # Mock embedder
    def mock_embed(texts):
        return [[0.1] * 384 for _ in texts]
    
    monkeypatch.setattr("ingest.embedder.get_embedder", lambda: type('obj', (object,), {'embed': mock_embed})())
    
    response = client.post("/admin/reindex/all")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["total"] == 3
    assert "started" in data["message"].lower()


def test_reindex_document_not_found(client):
    """Test reindex single document when document doesn't exist"""
    fake_id = str(uuid.uuid4())
    response = client.post(f"/admin/reindex/{fake_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_reindex_document_no_file(client, sample_document, monkeypatch):
    """Test reindex single document when file is missing"""
    # Update document to have no s3_path
    db = get_db_session()
    try:
        doc = db.query(Document).filter(Document.id == uuid.UUID(sample_document)).first()
        doc.s3_path = None
        db.commit()
    finally:
        db.close()
    
    response = client.post(f"/admin/reindex/{sample_document}")
    assert response.status_code == 400
    assert "file not found" in response.json()["detail"].lower()


def test_reindex_document_success(client, sample_document, tmp_path, monkeypatch):
    """Test successful reindex of a single document"""
    # Create dummy PDF file
    pdf_path = create_dummy_pdf(tmp_path, "test_nda.pdf")
    
    # Mock storage service to return the PDF file
    def mock_download_file(bucket, object_name):
        return pdf_path.read_bytes()
    
    monkeypatch.setattr(
        "api.services.service_registry.get_storage_service",
        lambda: type('obj', (object,), {'download_file': mock_download_file})()
    )
    
    # Mock parser and extractor
    def fake_parse(_file_path: str):
        return {
            "text": "Test PDF Document content",
            "pages": [{
                "page_num": 1,
                "text": "Test PDF Document content",
                "is_scanned": False,
                "span_start": 0,
                "span_end": 25,
            }],
            "metadata": {},
        }
    
    def fake_extract(_full_text, _pages):
        return {
            "title": "Test NDA",
            "recitals": [],
            "clauses": [],
            "metadata": {},
        }
    
    monkeypatch.setattr("ingest.parser.parser.parse", fake_parse)
    monkeypatch.setattr("ingest.clause_extractor.clause_extractor.extract", fake_extract)
    monkeypatch.setattr("ingest.ocr_detector.ocr_detector.needs_ocr", lambda pages: False)
    
    # Mock indexers
    def mock_index_document(*args, **kwargs):
        return True
    
    def mock_index_chunks(*args, **kwargs):
        return True
    
    monkeypatch.setattr("ingest.indexer_opensearch.opensearch_indexer.index_document", mock_index_document)
    monkeypatch.setattr("ingest.indexer_qdrant.qdrant_indexer.index_document", mock_index_document)
    monkeypatch.setattr("ingest.indexer_opensearch.opensearch_indexer.index_chunks", mock_index_chunks)
    monkeypatch.setattr("ingest.indexer_qdrant.qdrant_indexer.index_chunks", mock_index_chunks)
    
    # Mock embedder
    def mock_embed(texts):
        return [[0.1] * 384 for _ in texts]
    
    monkeypatch.setattr("ingest.embedder.get_embedder", lambda: type('obj', (object,), {'embed': mock_embed})())
    
    response = client.post(f"/admin/reindex/{sample_document}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "completed" in data["message"].lower()


def test_reindex_all_already_running(client, multiple_documents, monkeypatch):
    """Test that reindex all returns appropriate message when already running"""
    # Mock indexers
    def mock_index_document(*args, **kwargs):
        return True
    
    def mock_index_chunks(*args, **kwargs):
        return True
    
    monkeypatch.setattr("ingest.indexer_opensearch.opensearch_indexer.index_document", mock_index_document)
    monkeypatch.setattr("ingest.indexer_qdrant.qdrant_indexer.index_document", mock_index_document)
    monkeypatch.setattr("ingest.indexer_opensearch.opensearch_indexer.index_chunks", mock_index_chunks)
    monkeypatch.setattr("ingest.indexer_qdrant.qdrant_indexer.index_chunks", mock_index_chunks)
    
    # Mock embedder
    def mock_embed(texts):
        return [[0.1] * 384 for _ in texts]
    
    monkeypatch.setattr("ingest.embedder.get_embedder", lambda: type('obj', (object,), {'embed': mock_embed})())
    
    # Start first reindex
    response1 = client.post("/admin/reindex/all")
    assert response1.status_code == 200
    
    # Try to start second reindex immediately
    response2 = client.post("/admin/reindex/all")
    assert response2.status_code == 200
    data = response2.json()
    assert data["status"] == "already_running"
    assert "already in progress" in data["message"].lower()

