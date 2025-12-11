import fitz
import tempfile


def make_simple_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def test_ocr_pdf(mcp_servers):
    pdf_bytes = make_simple_pdf("Hello OCR")
    files = {"file": ("sample.pdf", pdf_bytes, "application/pdf")}
    import httpx

    resp = httpx.post(f"{mcp_servers['ocr_url']}/ocr_pdf", files=files, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    assert "pages" in data and len(data["pages"]) >= 1
    assert "hello" in data["pages"][0].lower()


def test_rag_ingest_and_query(mcp_servers):
    import httpx

    payload = {
        "doc_id": "doc1",
        "filename": "doc1.pdf",
        "text": "This is a distributor agreement between A and B.",
        "metadata": {"doc_type": "distributor_agreement"},
    }
    resp = httpx.post(f"{mcp_servers['rag_url']}/ingest", json=payload, timeout=30)
    resp.raise_for_status()
    q = httpx.post(
        f"{mcp_servers['rag_url']}/query",
        json={"query": "What type of document?", "n": 2},
        timeout=30,
    )
    q.raise_for_status()
    data = q.json()
    assert data["results"], "No RAG results returned"


def test_llm_classify_extract(mcp_servers):
    import httpx

    text = "This NDA is made between Foo Corp and Bar LLC effective Jan 1 2024."
    resp = httpx.post(
        f"{mcp_servers['llm_url']}/classify_and_extract",
        json={"text": text},
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    assert "classification" in data
    assert "extraction" in data

