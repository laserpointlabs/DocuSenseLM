import os
import subprocess
import time
import pytest
import httpx


def wait_for_server(url: str, timeout: int = 20):
    """Wait for a server to be ready by checking if it responds."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(url, timeout=2)
            if resp.status_code < 500:
                return True
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException):
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def mcp_servers():
    """Start both MCP servers and ensure they're ready before tests."""
    ocr_port = "7001"
    rag_port = "7002"
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    python_dir = os.path.join(project_root, "python")
    
    env = dict(os.environ)
    env["MCP_OCR_PORT"] = ocr_port
    env["MCP_RAG_PORT"] = rag_port
    # Add python directory to PYTHONPATH so modules can be found
    pythonpath = env.get("PYTHONPATH", "")
    if pythonpath:
        env["PYTHONPATH"] = f"{python_dir}{os.pathsep}{pythonpath}"
    else:
        env["PYTHONPATH"] = python_dir
    
    # Start OCR server
    ocr_proc = subprocess.Popen(
        ["python", "-m", "mcp_ocr_server.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=project_root,
    )
    
    # Start RAG server
    rag_proc = subprocess.Popen(
        ["python", "-m", "mcp_rag_server.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=project_root,
    )
    
    # Give servers a moment to start (easyocr can take time to initialize)
    time.sleep(5)
    
    try:
        # Wait for servers to be ready (OCR may take longer due to easyocr initialization)
        ocr_ready = wait_for_server(f"http://localhost:{ocr_port}/ocr_page", timeout=60)
        rag_ready = wait_for_server(f"http://localhost:{rag_port}/query", timeout=30)
        
        if not ocr_ready:
            # Check if process is still running
            if ocr_proc.poll() is not None:
                _, stderr = ocr_proc.communicate()
                raise RuntimeError(
                    f"OCR server on port {ocr_port} exited with code {ocr_proc.returncode}. "
                    f"Stderr: {stderr.decode('utf-8', errors='ignore')}"
                )
            raise RuntimeError(f"OCR server on port {ocr_port} did not become ready")
        if not rag_ready:
            # Check if process is still running
            if rag_proc.poll() is not None:
                _, stderr = rag_proc.communicate()
                raise RuntimeError(
                    f"RAG server on port {rag_port} exited with code {rag_proc.returncode}. "
                    f"Stderr: {stderr.decode('utf-8', errors='ignore')}"
                )
            raise RuntimeError(f"RAG server on port {rag_port} did not become ready")
        
        yield {
            "ocr_url": f"http://localhost:{ocr_port}",
            "rag_url": f"http://localhost:{rag_port}",
        }
    finally:
        # Cleanup: terminate both processes
        for proc in [ocr_proc, rag_proc]:
            if proc.poll() is None:  # Still running
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

