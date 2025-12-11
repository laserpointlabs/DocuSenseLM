import os
import time
import subprocess
import httpx
import pytest
import fitz


def make_simple_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    return doc.tobytes()


def wait_for_server(url: str, method: str = "GET", data=None, files=None, timeout: int = 90):
    start = time.time()
    while time.time() - start < timeout:
        try:
            if method == "POST":
                resp = httpx.post(url, json=data, files=files, timeout=60)
            else:
                resp = httpx.get(url, timeout=5)
            if resp.status_code < 500:
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(f"Server at {url} did not become ready")


@pytest.fixture(scope="session")
def mcp_servers():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    env_base = os.environ.copy()
    env_base["PYTHONPATH"] = os.path.join(root, "python")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY required for MCP integration tests")

    procs = []
    servers = {
        "ocr": ("mcp_ocr_server.main", 7001, {}),
        "rag": ("mcp_rag_server.main", 7002, {"OPENAI_API_KEY": api_key}),
        "llm": ("mcp_llm_server.main", 7003, {"OPENAI_API_KEY": api_key}),
    }

    for name, (module, port, extra_env) in servers.items():
        env = env_base.copy()
        env.update(extra_env)
        if name == "ocr":
            env["MCP_OCR_PORT"] = str(port)
        elif name == "rag":
            env["MCP_RAG_PORT"] = str(port)
        elif name == "llm":
            env["MCP_LLM_PORT"] = str(port)
        proc = subprocess.Popen(
            ["python", "-m", module],
            cwd=root,
            env=env,
            stdout=open(f"{module.replace('.', '_')}.log", "w"),
            stderr=subprocess.STDOUT,
        )
        procs.append((proc, module, port))

    try:
        time.sleep(2)
        # OCR readiness: actual PDF OCR to warm EasyOCR
        pdf_bytes = make_simple_pdf("ready")
        files = {"file": ("ready.pdf", pdf_bytes, "application/pdf")}
        wait_for_server("http://localhost:7001/ocr_pdf", method="POST", files=files, timeout=180)

        # RAG readiness: trivial query
        wait_for_server("http://localhost:7002/query")

        # LLM readiness: simple classify call
        wait_for_server(
            "http://localhost:7003/classify",
            method="POST",
            data={"text": "test"},
            timeout=60,
        )

        yield {
            "ocr_url": "http://localhost:7001",
            "rag_url": "http://localhost:7002",
            "llm_url": "http://localhost:7003",
        }
    finally:
        for proc, _, _ in procs:
            proc.terminate()
        for proc, _, _ in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

