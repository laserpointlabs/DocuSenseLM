import os
import sys
import json
import time
import shutil
import tempfile
import importlib

import fitz
import pytest
from fastapi.testclient import TestClient


def make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


@pytest.fixture
def temp_env(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    monkeypatch.setenv("USER_DATA_DIR", tmpdir)
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_upload_processes_via_mcp(mcp_servers, temp_env, monkeypatch):
    # Point backend at running MCP servers
    monkeypatch.setenv("MCP_OCR_URL", mcp_servers["ocr_url"])
    monkeypatch.setenv("MCP_RAG_URL", mcp_servers["rag_url"])
    monkeypatch.setenv("MCP_LLM_URL", mcp_servers["llm_url"])
    monkeypatch.setenv("MCP_START_SERVERS", "0")  # rely on fixture servers

    # Reload server with fresh env
    if "server" in sys.modules:
        del sys.modules["server"]
    import server  # noqa: F401
    importlib.reload(server)

    client = TestClient(server.app)

    pdf_bytes = make_pdf("Distributor agreement between Foo and Bar effective 2024")
    files = {"file": ("doc.pdf", pdf_bytes, "application/pdf")}
    resp = client.post("/upload", files=files, data={"doc_type": "nda"})
    assert resp.status_code == 200

    metadata_path = os.path.join(server.DOCUMENTS_DIR, "metadata.json")

    # Wait for background processing to complete
    deadline = time.time() + 90
    while time.time() < deadline:
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                data = json.load(f)
            if "doc.pdf" in data and data["doc.pdf"].get("status") == "processed":
                extraction = data["doc.pdf"].get("extraction", {})
                assert isinstance(extraction, dict)
                return
        time.sleep(2)

    raise AssertionError("Document was not processed via MCP within timeout")


