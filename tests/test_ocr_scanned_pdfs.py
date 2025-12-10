"""
Test OCR functionality on scanned PDFs.
This verifies that the MCP OCR server can extract text from scanned documents.
"""
import os
import tempfile
import shutil
from pathlib import Path
import pytest
import httpx
import fitz  # PyMuPDF


def make_test_pdf_with_text(path: Path, text: str):
    """Create a simple PDF with text for testing."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    doc.save(path)
    doc.close()


def test_ocr_server_responds(mcp_servers):
    """Test that OCR server is running and responds."""
    ocr_url = mcp_servers["ocr_url"]
    
    # Create test PDF in temp directory
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "test.pdf")
    
    try:
        make_test_pdf_with_text(Path(tmp_path), "Test Document\nThis is a test.")
        
        with open(tmp_path, "rb") as f:
            files = {"file": ("test.pdf", f.read(), "application/pdf")}
            resp = httpx.post(f"{ocr_url}/ocr_pdf", files=files, timeout=120)
        
        assert resp.status_code == 200, f"OCR server returned {resp.status_code}"
        data = resp.json()
        assert "pages" in data, "Response should contain 'pages'"
        assert len(data["pages"]) > 0, "Should extract at least one page"
        print(f"✅ OCR server responded correctly")
        print(f"   Extracted text: {data['pages'][0][:100]}...")
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_classify_snippet_endpoint(mcp_servers):
    """Test the classify_snippet endpoint used for document classification."""
    ocr_url = mcp_servers["ocr_url"]
    
    # Create test PDF in temp directory
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "test_nda.pdf")
    
    try:
        make_test_pdf_with_text(
            Path(tmp_path),
            "MUTUAL NON-DISCLOSURE AGREEMENT\n\nThis agreement is between..."
        )
        
        with open(tmp_path, "rb") as f:
            files = {"file": ("test_nda.pdf", f.read(), "application/pdf")}
            resp = httpx.post(f"{ocr_url}/classify_snippet", files=files, timeout=120)
        
        assert resp.status_code == 200, f"classify_snippet returned {resp.status_code}"
        data = resp.json()
        assert "snippet" in data, "Response should contain 'snippet'"
        snippet = data["snippet"]
        assert len(snippet) > 0, "Should extract snippet text"
        assert "NON-DISCLOSURE" in snippet.upper() or "AGREEMENT" in snippet.upper(), \
            f"Snippet should contain document type: {snippet[:200]}"
        print(f"✅ classify_snippet endpoint works")
        print(f"   Snippet: {snippet[:150]}...")
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_ocr_full_document(mcp_servers):
    """Test OCR on a full multi-page document."""
    ocr_url = mcp_servers["ocr_url"]
    
    # Create test PDF in temp directory
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "multipage.pdf")
    
    try:
        doc = fitz.open()
        for i in range(3):
            page = doc.new_page()
            page.insert_text((50, 50), f"Page {i+1}\n\nThis is page {i+1} of the test document.")
        doc.save(tmp_path)
        doc.close()
        
        with open(tmp_path, "rb") as f:
            files = {"file": ("multipage.pdf", f.read(), "application/pdf")}
            resp = httpx.post(f"{ocr_url}/ocr_pdf", files=files, timeout=180)
        
        assert resp.status_code == 200, f"OCR returned {resp.status_code}"
        data = resp.json()
        assert "pages" in data, "Response should contain 'pages'"
        assert len(data["pages"]) == 3, f"Should extract 3 pages, got {len(data['pages'])}"
        
        # Verify each page has content
        for i, page_text in enumerate(data["pages"]):
            assert len(page_text) > 0, f"Page {i+1} should have content"
            assert f"Page {i+1}" in page_text, f"Page {i+1} should contain 'Page {i+1}'"
        
        print(f"✅ OCR extracted all pages correctly")
        print(f"   Pages extracted: {len(data['pages'])}")
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

