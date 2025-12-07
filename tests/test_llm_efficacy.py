import pytest
import requests
import time
import os
import json
import re
from datetime import datetime

# Configuration
API_URL = "http://localhost:14242"
TEST_FILE = "data/green_nda.pdf"
FILENAME = "green_nda.pdf"

# Ground Truth Data for green_nda.pdf
EXPECTED_FACTS = {
    "expiration_date": "2028", 
    "parties": ["Green", "Boston"], 
    "termination_period": "3 years"
}

@pytest.fixture(scope="module")
def setup_document():
    """Uploads the document and waits for processing to complete."""
    # Cleanup specific file to ensure fresh upload state
    requests.delete(f"{API_URL}/documents/{FILENAME}")
    
    with open(TEST_FILE, "rb") as f:
        files = {"file": (FILENAME, f, "application/pdf")}
        requests.post(f"{API_URL}/upload", files=files, params={"doc_type": "nda"})
    
    print("Waiting for LLM processing...")
    for _ in range(30):
        res = requests.get(f"{API_URL}/documents")
        data = res.json()
        if FILENAME in data and data[FILENAME]["status"] == "processed":
            return data[FILENAME]
        time.sleep(2)
    
    pytest.fail("Document failed to process within timeout")

def test_competency_extraction_accuracy(setup_document):
    answers = setup_document.get("competency_answers", {})
    print(f"\nExtracted Answers: {json.dumps(answers, indent=2)}")
    
    exp_date = answers.get("expiration_date", "")
    assert EXPECTED_FACTS["expiration_date"] in str(exp_date), \
        f"Expected {EXPECTED_FACTS['expiration_date']} in expiration date, got '{exp_date}'"

    found_party = False
    all_values = " ".join([str(v) for v in answers.values()]).lower()
    for party in EXPECTED_FACTS["parties"]:
        if party.lower() in all_values:
            found_party = True
            break
    assert found_party, f"Could not find expected parties {EXPECTED_FACTS['parties']} in extracted metadata"

def test_rag_retrieval_efficacy(setup_document):
    # Use specific query to target this document in a potentially shared vector DB
    query = "What is the termination clause in the Green NDA?"
    res = requests.post(f"{API_URL}/chat", json={"question": query})
    data = res.json()
    sources = data.get("sources", [])
    assert FILENAME in sources, f"RAG failed to cite {FILENAME} as a source."

def test_chat_response_quality(setup_document):
    query = "How long is the term of the Green NDA?"
    res = requests.post(f"{API_URL}/chat", json={"question": query})
    data = res.json()
    answer = data.get("answer", "").lower()
    
    print(f"\nQ: {query}\nA: {answer}")
    
    # Robust check for "3 years" in various formats
    term_pattern = r"(three|3)\s*(\(\d+\))?\s*years"
    assert re.search(term_pattern, answer) or "2028" in answer, \
        "LLM failed to answer with the correct term duration (expected '3 years')"

def test_hallucination_check(setup_document):
    query = "What is the specific budget for the 'Project Mars' initiative in the Green NDA?"
    res = requests.post(f"{API_URL}/chat", json={"question": query})
    data = res.json()
    answer = data.get("answer", "").lower()
    
    print(f"\nQ: {query}\nA: {answer}")
    
    safe_phrases = [
        "does not mention", "no information", "cannot find", 
        "not specified", "sorry", "does not contain", 
        "unable to answer", "not possible to answer"
    ]
    assert any(p in answer for p in safe_phrases), \
        "LLM may have hallucinated an answer to a non-existent topic."

def test_report_efficacy(setup_document):
    res = requests.post(f"{API_URL}/report")
    data = res.json()
    report = data.get("report", "")
    assert "Subject Line:" in report
    assert FILENAME in report, "Generated report failed to mention the file."
