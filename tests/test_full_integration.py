"""
Full integration test: Upload, classify, extract, and query documents.
This tests the complete workflow from document upload to querying.
"""
import os
import tempfile
import shutil
from pathlib import Path
import pytest
import httpx
import fitz  # PyMuPDF


def make_test_pdf(path: Path, text: str, doc_type: str = "test"):
    """Create a test PDF with specified text."""
    doc = fitz.open()
    page = doc.new_page()
    # Add document type header
    if doc_type == "nda":
        header = "MUTUAL NON-DISCLOSURE AGREEMENT\n\n"
    elif doc_type == "distributor":
        header = "DISTRIBUTOR AGREEMENT\n\n"
    elif doc_type == "sales":
        header = "SALES AGREEMENT\n\n"
    else:
        header = ""
    
    page.insert_text((50, 50), header + text)
    doc.save(path)
    doc.close()


def test_full_workflow(mcp_servers):
    """Test complete workflow: upload -> classify -> extract -> query."""
    ocr_url = mcp_servers["ocr_url"]
    rag_url = mcp_servers["rag_url"]
    
    # Step 1: Create a test document
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "test_nda.pdf")
    
    try:
        make_test_pdf(
            Path(tmp_path),
            "This is a test NDA document.\nEffective Date: January 1, 2024\nExpiration Date: January 1, 2025",
            doc_type="nda"
        )
        # Step 2: Test OCR extraction
        print("\n📄 Step 1: Testing OCR extraction...")
        with open(tmp_path, "rb") as f:
            files = {"file": ("test_nda.pdf", f.read(), "application/pdf")}
            resp = httpx.post(f"{ocr_url}/ocr_pdf", files=files, timeout=60)
        
        assert resp.status_code == 200, f"OCR failed: {resp.status_code}"
        ocr_data = resp.json()
        assert "pages" in ocr_data and len(ocr_data["pages"]) > 0
        extracted_text = "\n".join(ocr_data["pages"])
        print(f"   ✅ Extracted {len(extracted_text)} characters")
        assert "NDA" in extracted_text.upper() or "NON-DISCLOSURE" in extracted_text.upper()
        
        # Step 3: Test classification snippet
        print("\n🔍 Step 2: Testing classification snippet...")
        with open(tmp_path, "rb") as f:
            files = {"file": ("test_nda.pdf", f.read(), "application/pdf")}
            resp = httpx.post(f"{ocr_url}/classify_snippet", files=files, timeout=60)
        
        assert resp.status_code == 200
        snippet_data = resp.json()
        assert "snippet" in snippet_data
        snippet = snippet_data["snippet"]
        print(f"   ✅ Extracted snippet: {snippet[:100]}...")
        
        # Step 4: Test RAG ingestion
        print("\n📚 Step 3: Testing RAG ingestion...")
        ingest_resp = httpx.post(
            f"{rag_url}/ingest",
            json={
                "doc_id": "test_doc_123",
                "filename": "test_nda.pdf",
                "text": extracted_text,
                "chunk_size": 500,
                "chunk_overlap": 100,
                "metadata": {"doc_type": "nda", "test": True}
            },
            timeout=30
        )
        
        assert ingest_resp.status_code == 200, f"Ingest failed: {ingest_resp.status_code}"
        ingest_data = ingest_resp.json()
        assert ingest_data.get("status") == "ok"
        assert ingest_data.get("chunks", 0) > 0
        print(f"   ✅ Ingested {ingest_data.get('chunks')} chunks")
        
        # Step 5: Test RAG query
        print("\n🔎 Step 4: Testing RAG query...")
        query_resp = httpx.post(
            f"{rag_url}/query",
            json={
                "query": "What is the expiration date?",
                "n": 3
            },
            timeout=30
        )
        
        assert query_resp.status_code == 200, f"Query failed: {query_resp.status_code}"
        query_data = query_resp.json()
        assert "results" in query_data
        assert len(query_data["results"]) > 0
        print(f"   ✅ Found {len(query_data['results'])} relevant chunks")
        
        # Verify results contain relevant information
        results_text = " ".join([r["text"] for r in query_data["results"]])
        assert "2025" in results_text or "expiration" in results_text.lower()
        
        print("\n✅ Full workflow test passed!")
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

