import httpx


def test_mcp_servers_start_and_healthcheck(mcp_servers):
    """Test that both MCP servers are running and reachable."""
    ocr_url = mcp_servers["ocr_url"]
    rag_url = mcp_servers["rag_url"]
    
    # Test OCR server - should respond to POST /ocr_page
    try:
        resp = httpx.get(f"{ocr_url}/ocr_page", timeout=5)
        # GET might return 405 (method not allowed) or 422 (missing file), but not connection error
        assert resp.status_code < 500, f"OCR server returned error: {resp.status_code}"
    except httpx.ConnectError:
        assert False, "OCR server not reachable"
    
    # Test RAG server - POST endpoint, GET should return 405 or 404
    try:
        resp = httpx.get(f"{rag_url}/query", timeout=5)
        assert resp.status_code in (404, 405), f"RAG server returned unexpected status: {resp.status_code}"
    except httpx.ConnectError:
        assert False, "RAG server not reachable"

