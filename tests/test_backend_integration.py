"""
Test the full backend server integration with MCP servers.
This verifies the complete upload -> classify -> extract workflow.
"""
import os
import sys
import time
import tempfile
import shutil
from pathlib import Path
import pytest
import httpx
import fitz  # PyMuPDF

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))


def make_test_pdf(path: Path, text: str, doc_type: str = "test"):
    """Create a test PDF with specified text."""
    doc = fitz.open()
    page = doc.new_page()
    if doc_type == "nda":
        header = "MUTUAL NON-DISCLOSURE AGREEMENT\n\n"
    elif doc_type == "distributor":
        header = "DISTRIBUTOR AGREEMENT\n\n"
    else:
        header = ""
    page.insert_text((50, 50), header + text)
    doc.save(path)
    doc.close()


@pytest.fixture(scope="module")
def backend_server(mcp_servers):
    """Start the backend server for testing."""
    import subprocess
    import os
    
    # Set environment variables
    env = dict(os.environ)
    env["MCP_OCR_URL"] = mcp_servers["ocr_url"]
    env["MCP_RAG_URL"] = mcp_servers["rag_url"]
    env["PORT"] = "8000"
    
    # Start backend server
    project_root = Path(__file__).parent.parent
    python_dir = project_root / "python"
    
    # Add python directory to PYTHONPATH
    pythonpath = env.get("PYTHONPATH", "")
    if pythonpath:
        env["PYTHONPATH"] = f"{python_dir}{os.pathsep}{pythonpath}"
    else:
        env["PYTHONPATH"] = str(python_dir)
    
    proc = subprocess.Popen(
        ["python", "-m", "server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(project_root),
    )
    
    # Wait for server to start
    backend_url = "http://localhost:8000"
    for _ in range(30):
        try:
            resp = httpx.get(f"{backend_url}/health", timeout=2)
            if resp.status_code == 200:
                break
        except:
            time.sleep(1)
    else:
        proc.terminate()
        pytest.fail("Backend server did not start")
    
    yield {"url": backend_url, "proc": proc}
    
    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def test_backend_health(backend_server):
    """Test that backend server is healthy."""
    resp = httpx.get(f"{backend_server['url']}/health", timeout=5)
    assert resp.status_code == 200
    print("✅ Backend server is healthy")


def test_upload_and_classify(backend_server, mcp_servers):
    """Test uploading a document and verifying it gets classified."""
    backend_url = backend_server["url"]
    
    # Create test PDF
    tmp_dir = tempfile.mkdtemp()
    test_pdf = Path(tmp_dir) / "test_nda.pdf"
    
    try:
        make_test_pdf(
            test_pdf,
            "This is a test NDA.\nEffective Date: 2024-01-01\nExpiration Date: 2025-01-01",
            doc_type="nda"
        )
        
        # Upload document
        print(f"\n📤 Uploading document...")
        with open(test_pdf, "rb") as f:
            files = {"file": ("test_nda.pdf", f.read(), "application/pdf")}
            data = {"doc_type": "auto"}  # Auto-classify
            resp = httpx.post(
                f"{backend_url}/documents/upload",
                files=files,
                data=data,
                timeout=180  # OCR can take time
            )
        
        assert resp.status_code == 200, f"Upload failed: {resp.status_code} - {resp.text}"
        upload_data = resp.json()
        print(f"   ✅ Document uploaded: {upload_data.get('filename')}")
        
        # Verify document was classified
        filename = upload_data.get("filename")
        assert filename, "Should return filename"
        
        # Get document info
        doc_resp = httpx.get(f"{backend_url}/documents/{filename}", timeout=10)
        assert doc_resp.status_code == 200
        doc_data = doc_resp.json()
        
        doc_type = doc_data.get("doc_type", "unknown")
        print(f"   📋 Document type: {doc_type}")
        assert doc_type != "unknown", "Document should be classified"
        
        print("   ✅ Document successfully uploaded and classified")
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

