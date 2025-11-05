#!/usr/bin/env python3
"""
End-to-end test script for the full NDA Dashboard workflow:
1. File Upload
2. Processing/Ingestion
3. Competency Question Building & Testing
4. Search
5. Ask Question

This script validates the complete user journey.
"""
import os
import sys
import time
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# API base URL
API_BASE = os.getenv("API_URL", "http://localhost:8000")
TIMEOUT = 300  # 5 minutes for processing


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_step(step_num: int, description: str):
    """Print a test step header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}")
    print(f"Step {step_num}: {description}")
    print(f"{'='*60}{Colors.RESET}")


def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_warning(message: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")


def print_info(message: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")


def wait_for_document_processing(doc_id: str, max_wait: int = 300) -> bool:
    """Wait for document to be processed"""
    print_info(f"Waiting for document {doc_id[:8]}... to be processed (max {max_wait}s)")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        response = requests.get(f"{API_BASE}/documents/{doc_id}")
        if response.status_code == 200:
            doc = response.json()
            status = doc.get('status')

            if status == 'PROCESSED':
                print_success(f"Document processed successfully")
                return True
            elif status == 'FAILED':
                print_error(f"Document processing failed: {doc.get('error', 'Unknown error')}")
                return False
            else:
                print_info(f"Status: {status}... waiting")

        time.sleep(2)

    print_error(f"Document processing timeout after {max_wait}s")
    return False


def test_upload_document(file_path: str) -> Optional[str]:
    """Test 1: Upload a document"""
    print_step(1, "File Upload")

    if not os.path.exists(file_path):
        print_error(f"File not found: {file_path}")
        return None

    print_info(f"Uploading: {file_path}")

    try:
        # Upload endpoint expects files named 'files' (plural, for batch upload)
        with open(file_path, 'rb') as file_data:
            files = [('files', (os.path.basename(file_path), file_data, 'application/pdf'))]
            response = requests.post(
                f"{API_BASE}/upload",
                files=files,
                timeout=60
            )

        if response.status_code == 200:
            result = response.json()
            # Response is a list for batch upload
            if isinstance(result, list) and len(result) > 0:
                doc = result[0]
            else:
                doc = result

            doc_id = doc.get('document_id')
            if not doc_id:
                doc_id = doc.get('id')

            print_success(f"Document uploaded: {doc_id}")
            print_info(f"Filename: {doc.get('filename')}")
            print_info(f"Status: {doc.get('status')}")
            return doc_id
        else:
            print_error(f"Upload failed: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print_error(f"Upload error: {e}")
        return None


def test_document_processing(doc_id: str) -> bool:
    """Test 2: Wait for document processing"""
    print_step(2, "Document Processing/Ingestion")

    if not wait_for_document_processing(doc_id):
        return False

    # Verify document details
    response = requests.get(f"{API_BASE}/documents/{doc_id}")
    if response.status_code == 200:
        doc = response.json()
        print_info(f"Document ID: {doc_id}")
        print_info(f"Filename: {doc.get('filename')}")
        print_info(f"Status: {doc.get('status')}")

        # Check metadata
        metadata = doc.get('metadata', {})
        if metadata:
            print_info(f"Effective Date: {metadata.get('effective_date')}")
            print_info(f"Governing Law: {metadata.get('governing_law')}")
            print_info(f"Term: {metadata.get('term_months')} months")
            print_info(f"Is Mutual: {metadata.get('is_mutual')}")

            parties = metadata.get('parties', [])
            if parties:
                print_info(f"Parties found: {len(parties)}")
                for party in parties:
                    print_info(f"  - {party.get('name', 'N/A')} ({party.get('type', 'N/A')})")
            else:
                print_warning("No parties found in metadata")

        return True
    else:
        print_error(f"Failed to get document details: {response.status_code}")
        return False


def test_search(doc_id: str) -> bool:
    """Test 3: Test search functionality"""
    print_step(3, "Search Functionality")

    # Test various search queries
    test_queries = [
        "effective date",
        "governing law",
        "term",
        "confidential information",
    ]

    success_count = 0

    for query in test_queries:
        print_info(f"Searching: '{query}'")
        try:
            response = requests.post(
                f"{API_BASE}/search",
                json={"query": query, "k": 5},
                timeout=30
            )

            if response.status_code == 200:
                results = response.json()
                hits = results.get('hits', [])
                print_success(f"Found {len(hits)} results")

                if hits:
                    # Show top result
                    top_hit = hits[0]
                    print_info(f"  Top result: doc_id={top_hit.get('doc_id', '')[:8]}..., "
                              f"clause={top_hit.get('clause_number')}, "
                              f"page={top_hit.get('page_num')}, "
                              f"score={top_hit.get('score', 0):.3f}")
                    success_count += 1
                else:
                    print_warning("No results found")
            else:
                print_error(f"Search failed: {response.status_code} - {response.text}")

        except Exception as e:
            print_error(f"Search error: {e}")

    if success_count > 0:
        print_success(f"Search test: {success_count}/{len(test_queries)} queries successful")
        return True
    else:
        print_error("All search queries failed")
        return False


def test_ask_question(doc_id: str) -> bool:
    """Test 4: Test Ask Question functionality"""
    print_step(4, "Ask Question Functionality")

    # Test various questions
    test_questions = [
        "What is the effective date?",
        "What is the governing law?",
        "What is the term of the agreement?",
    ]

    success_count = 0

    for question in test_questions:
        print_info(f"Question: '{question}'")
        try:
            response = requests.post(
                f"{API_BASE}/answer",
                json={"question": question, "max_context_chunks": 10},
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                answer = result.get('answer', '')
                citations = result.get('citations', [])

                print_success(f"Answer: {answer}")
                print_info(f"Citations: {len(citations)}")

                if citations:
                    for i, cit in enumerate(citations[:3], 1):
                        print_info(f"  {i}. doc_id={cit.get('doc_id', '')[:8]}..., "
                                  f"clause={cit.get('clause_number')}, "
                                  f"page={cit.get('page_num')}")

                if answer and not answer.lower().startswith('i cannot find'):
                    success_count += 1
                else:
                    print_warning("Answer indicates information not found")
            else:
                print_error(f"Answer failed: {response.status_code} - {response.text}")

        except Exception as e:
            print_error(f"Answer error: {e}")

    if success_count > 0:
        print_success(f"Ask Question test: {success_count}/{len(test_questions)} questions successful")
        return True
    else:
        print_error("All questions failed")
        return False


def test_competency_questions(doc_id: str) -> bool:
    """Test 5: Competency Question Building & Testing"""
    print_step(5, "Competency Question Building & Testing")

    # Create a test question
    test_question = {
        "question_text": "What is the effective date of this NDA?",
        "expected_answer_text": "Date from document",
        "confidence_threshold": 0.7
    }

    print_info("Creating competency question...")
    try:
        response = requests.post(
            f"{API_BASE}/competency/questions",
            json=test_question,
            timeout=30
        )

        if response.status_code == 200:
            question = response.json()
            question_id = question.get('id')
            print_success(f"Question created: {question_id}")

            # Wait a moment for question to be saved
            time.sleep(1)

            # Run test
            print_info("Running test...")
            test_response = requests.post(
                f"{API_BASE}/competency/test/{question_id}",
                timeout=60
            )

            if test_response.status_code == 200:
                test_result = test_response.json()
                print_success(f"Test completed")
                print_info(f"Answer: {test_result.get('answer', 'N/A')}")
                print_info(f"Confidence: {test_result.get('accuracy_score', 0):.2%}")
                print_info(f"Citations: {len(test_result.get('citations', []))}")

                # Clean up - delete the test question
                print_info("Cleaning up test question...")
                delete_response = requests.delete(
                    f"{API_BASE}/competency/questions/{question_id}",
                    timeout=30
                )
                if delete_response.status_code == 200:
                    print_success("Test question deleted")

                return True
            else:
                print_error(f"Test failed: {test_response.status_code} - {test_response.text}")
                return False
        else:
            print_error(f"Question creation failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print_error(f"Competency test error: {e}")
        return False


def test_party_address_search(doc_id: str) -> bool:
    """Test 6: Search for party address (specific test for the Vallen issue)"""
    print_step(6, "Party Address Search (Vallen Test)")

    # Get document details to find party name
    response = requests.get(f"{API_BASE}/documents/{doc_id}")
    if response.status_code != 200:
        print_error("Failed to get document details")
        return False

    doc = response.json()
    metadata = doc.get('metadata', {})
    parties = metadata.get('parties', [])

    if not parties:
        print_warning("No parties found in document metadata")
        return False

    # Try to find a party with a name
    party_name = None
    for party in parties:
        name = party.get('name', '')
        if name and len(name) > 3:
            party_name = name
            break

    if not party_name:
        print_warning("No valid party name found")
        return False

    print_info(f"Testing search for party: {party_name}")
    print_info(f"Query: 'What is the address of {party_name}?'")

    try:
        response = requests.post(
            f"{API_BASE}/answer",
            json={"question": f"What is the address of {party_name}?", "max_context_chunks": 10},
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            answer = result.get('answer', '')
            citations = result.get('citations', [])

            print_info(f"Answer: {answer}")
            print_info(f"Citations: {len(citations)}")

            # Check if answer is not hallucinated
            if answer and not answer.lower().startswith('i cannot find'):
                # Check if it's a real address (contains common address elements)
                if any(word in answer.lower() for word in ['street', 'st', 'avenue', 'ave', 'road', 'rd', 'drive', 'dr', 'city', 'state', 'zip']):
                    print_success("Answer appears to contain address information")
                    return True
                else:
                    print_warning("Answer doesn't look like an address")
                    return False
            else:
                print_warning("Answer indicates information not found - this is expected if party extraction failed")
                return False
        else:
            print_error(f"Answer failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print_error(f"Party address search error: {e}")
        return False


def main():
    """Run full workflow test"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}")
    print("NDA Dashboard - Full Workflow Test")
    print(f"{'='*60}{Colors.RESET}\n")

    # Find a test PDF file
    data_dir = Path(__file__).parent.parent / "data"
    pdf_files = list(data_dir.glob("*.pdf"))

    if not pdf_files:
        print_error("No PDF files found in data/ directory")
        print_info("Please add a PDF file to test with")
        return 1

    # Use the first PDF file
    test_file = pdf_files[0]
    print_info(f"Using test file: {test_file.name}")

    results = {
        'upload': False,
        'processing': False,
        'search': False,
        'ask_question': False,
        'competency': False,
        'party_address': False,
    }

    # Step 1: Upload
    doc_id = test_upload_document(str(test_file))
    if doc_id:
        results['upload'] = True
    else:
        print_error("Upload failed - cannot continue")
        return 1

    # Step 2: Processing
    if test_document_processing(doc_id):
        results['processing'] = True
    else:
        print_error("Processing failed - continuing with other tests")

    # Step 3: Search
    results['search'] = test_search(doc_id)

    # Step 4: Ask Question
    results['ask_question'] = test_ask_question(doc_id)

    # Step 5: Competency
    results['competency'] = test_competency_questions(doc_id)

    # Step 6: Party Address Search
    results['party_address'] = test_party_address_search(doc_id)

    # Summary
    print_step(7, "Test Summary")
    print(f"\n{Colors.BOLD}Results:{Colors.RESET}")
    for test_name, passed in results.items():
        status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
        print(f"  {test_name.replace('_', ' ').title():20} {status}")

    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)

    print(f"\n{Colors.BOLD}Overall: {passed_tests}/{total_tests} tests passed{Colors.RESET}")

    if passed_tests == total_tests:
        print(f"{Colors.GREEN}{Colors.BOLD}All tests passed! 🎉{Colors.RESET}")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}Some tests failed{Colors.RESET}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
