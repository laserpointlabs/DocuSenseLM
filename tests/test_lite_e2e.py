import os
import time
import requests
import pytest
import shutil

# Configuration
API_BASE_URL = "http://localhost:14242"
TEST_FILE_PATH = "data/green_nda.pdf"
TEST_FILENAME = "green_nda.pdf"

@pytest.fixture(scope="module")
def api_base_url():
    """Ensure the API is running before tests."""
    # Check health
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        assert response.status_code == 200
        return API_BASE_URL
    except requests.exceptions.ConnectionError:
        pytest.fail(f"API is not running at {API_BASE_URL}. Please start the backend server.")

def test_health_check(api_base_url):
    response = requests.get(f"{api_base_url}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

def test_config(api_base_url):
    response = requests.get(f"{api_base_url}/config")
    assert response.status_code == 200
    data = response.json()
    assert "document_types" in data

def test_upload_document(api_base_url):
    # Ensure file exists
    assert os.path.exists(TEST_FILE_PATH)
    
    with open(TEST_FILE_PATH, "rb") as f:
        files = {"file": (TEST_FILENAME, f, "application/pdf")}
        response = requests.post(
            f"{api_base_url}/upload", 
            files=files,
            params={"doc_type": "nda"}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "uploaded"
    assert data["filename"] == TEST_FILENAME

def test_list_documents(api_base_url):
    # Wait a moment for metadata to update
    time.sleep(1)
    response = requests.get(f"{api_base_url}/documents")
    assert response.status_code == 200
    data = response.json()
    assert TEST_FILENAME in data
    assert data[TEST_FILENAME]["status"] in ["pending", "processed", "reprocessing"]

def test_wait_for_processing(api_base_url):
    # Poll until processed (timeout 60s)
    max_retries = 30
    for _ in range(max_retries):
        response = requests.get(f"{api_base_url}/documents")
        data = response.json()
        if TEST_FILENAME in data and data[TEST_FILENAME]["status"] == "processed":
            return
        time.sleep(2)
    
    pytest.fail(f"Document {TEST_FILENAME} failed to process within timeout")

def test_chat(api_base_url):
    # Test simple chat
    payload = {"question": "What is the termination clause?"}
    response = requests.post(f"{api_base_url}/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    # Check if answer is meaningful (not just error)
    assert len(data["answer"]) > 10

def test_report(api_base_url):
    response = requests.post(f"{api_base_url}/report")
    assert response.status_code == 200
    data = response.json()
    assert "report" in data
    assert len(data["report"]) > 10

def test_reprocess(api_base_url):
    response = requests.post(f"{api_base_url}/reprocess/{TEST_FILENAME}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "reprocessing_started"
    
    # Wait for processing again
    test_wait_for_processing(api_base_url)

def test_delete_document(api_base_url):
    response = requests.delete(f"{api_base_url}/documents/{TEST_FILENAME}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    
    # Verify gone
    response = requests.get(f"{api_base_url}/documents")
    data = response.json()
    assert TEST_FILENAME not in data

