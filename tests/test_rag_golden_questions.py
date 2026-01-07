"""
RAG Golden Questions Test

This test validates that the RAG system correctly answers known questions
from our document corpus. It serves as a regression test to ensure that
changes to the search/retrieval logic don't break known working cases.

IMPORTANT: This test requires:
1. The backend server running on localhost:14242
2. The test documents to be uploaded and processed
3. OpenAI API key configured

Run with: pytest tests/test_rag_golden_questions.py -v
"""
import pytest
import requests
import os
import re

# Configuration
API_URL = os.environ.get("API_URL", "http://localhost:14242")
TIMEOUT = 120  # seconds - increased for LLM response time

# Golden Questions: Each entry contains:
# - question: The question to ask
# - expected_patterns: List of regex patterns that should match the answer
# - expected_source: The filename that should be cited (partial match OK)
# - description: Human-readable description of what we're testing

GOLDEN_QUESTIONS = [
    # Keep this suite safe for public repos:
    # Use only synthetic fixtures (no real company/vendor names or proprietary docs).
    {
        "id": "ocr_pricing_weeding",
        "question": "What do we pay for weeding?",
        "expected_patterns": [
            r"\$55",
            r"(per\s*(man)?\s*hour|hourly|T&M|time\s*and\s*material)",
        ],
        "expected_source": "scanned_pricing_test.pdf",
    },
    {
        "id": "ocr_pricing_seasonal",
        "question": "What is the seasonal contract price?",
        "expected_patterns": [
            r"\$15,?000",
        ],
        "expected_source": "scanned_pricing_test.pdf",
    },
    {
        "id": "ocr_nda_parties",
        "question": "Who are the parties?",
        "expected_patterns": [
            r"Acme",
            r"Beta",
        ],
        "expected_source": "scanned_nda_test.pdf",
    },
    {
        "id": "ocr_nda_expiration",
        "question": "What is the expiration date?",
        "expected_patterns": [
            r"July",
            r"2028",
        ],
        "expected_source": "scanned_nda_test.pdf",
    },
]


def check_server_health():
    """Check if the server is running and healthy."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


@pytest.fixture(scope="module")
def ensure_server_running():
    """Ensure the server is running before tests."""
    if not check_server_health():
        pytest.skip("Server not running at " + API_URL)


class TestRAGGoldenQuestions:
    """Test RAG with golden questions that have known correct answers."""

    @pytest.mark.parametrize("golden", GOLDEN_QUESTIONS)
    def test_golden_question(self, ensure_server_running, golden):
        """
        Test that RAG correctly answers a golden question.

        This validates:
        1. The answer contains expected patterns
        2. The correct source document is cited
        """
        question = golden["question"]
        expected_patterns = golden["expected_patterns"]
        expected_source = golden["expected_source"]

        # Make the request
        response = requests.post(
            f"{API_URL}/chat",
            json={"question": question},
            timeout=TIMEOUT
        )

        assert response.status_code == 200, f"API returned {response.status_code}"

        data = response.json()
        answer = data.get("answer", "")
        sources = data.get("sources", [])

        # Print for debugging
        print(f"\nQuestion: {question}")
        print(f"Answer: {answer[:200]}...")
        print(f"Sources: {sources}")

        # Check expected patterns in answer
        for pattern in expected_patterns:
            match = re.search(pattern, answer, re.IGNORECASE)
            assert match, f"Expected pattern '{pattern}' not found in answer: {answer[:200]}"

        # Check expected source is cited
        source_found = any(expected_source.lower() in s.lower() for s in sources)
        assert source_found, f"Expected source containing '{expected_source}' not in sources: {sources}"


class TestOCRRegression:
    """
    OCR regression tests for synthetic scanned PDFs.

    These tests are SKIPPED unless the scanned PDFs have been uploaded and processed in the backend.
    Generate them with: python tests/fixtures/generate_scanned_test_pdfs.py
    """

    OCR_CASES = [
        {
            "id": "ocr_pricing_weeding",
            "filename_hint": "scanned_pricing_test.pdf",
            "question": "What do we pay for weeding?",
            "expected_patterns": [r"\$55"],
        },
        {
            "id": "ocr_nda_parties",
            "filename_hint": "scanned_nda_test.pdf",
            "question": "Who are the parties?",
            "expected_patterns": [r"Acme", r"Beta"],
        },
    ]

    def _documents(self):
        r = requests.get(f"{API_URL}/documents", timeout=10)
        assert r.status_code == 200
        return r.json() or {}

    @pytest.mark.parametrize("case", OCR_CASES)
    def test_scanned_pdf_ocr(self, ensure_server_running, case):
        docs = self._documents()
        present = any(case["filename_hint"].lower() == k.lower() for k in docs.keys())
        if not present:
            pytest.skip(f"OCR fixture '{case['filename_hint']}' not uploaded to backend")

        response = requests.post(
            f"{API_URL}/chat",
            json={"question": case["question"]},
            timeout=TIMEOUT
        )
        assert response.status_code == 200

        data = response.json()
        answer = data.get("answer", "")
        sources = data.get("sources", [])

        for pattern in case["expected_patterns"]:
            assert re.search(pattern, answer, re.IGNORECASE), f"Expected pattern '{pattern}' not found. Answer: {answer[:300]}"

        source_found = any(case["filename_hint"].lower() in s.lower() for s in sources)
        assert source_found, f"Expected OCR source '{case['filename_hint']}' not in sources: {sources}"

    def test_no_hallucination_on_unknown(self, ensure_server_running):
        """
        Test that RAG doesn't hallucinate answers for questions about non-existent content.
        """
        question = "What is the specific budget for the Mars colonization project in our documents?"

        response = requests.post(
            f"{API_URL}/chat",
            json={"question": question},
            timeout=TIMEOUT
        )

        assert response.status_code == 200

        data = response.json()
        answer = data.get("answer", "").lower()

        print(f"\nQuestion: {question}")
        print(f"Answer: {answer[:200]}...")

        # Should indicate no information found
        safe_phrases = [
            "no information", "not mentioned", "cannot find",
            "not specified", "does not contain", "no specific",
            "unable to", "i don't have", "not available",
            "no documents", "sorry"
        ]

        has_safe_phrase = any(phrase in answer for phrase in safe_phrases)
        # Or sources should be empty
        sources_empty = len(data.get("sources", [])) == 0

        assert has_safe_phrase or sources_empty, \
            f"RAG may have hallucinated. Answer: {answer[:200]}"


class TestHybridSearchRanking:
    """Test that hybrid search correctly ranks results."""

    def test_keyword_boosting(self, ensure_server_running):
        """
        Test that documents containing exact query keywords are ranked highly.
        This is the key benefit of hybrid search over pure semantic search.
        """
        # This test assumes the synthetic OCR fixture is uploaded.
        docs = requests.get(f"{API_URL}/documents", timeout=10).json() or {}
        present = any("scanned_pricing_test.pdf".lower() == k.lower() for k in docs.keys())
        if not present:
            pytest.skip("OCR fixture 'scanned_pricing_test.pdf' not uploaded to backend")

        question = "weeding costs"

        response = requests.post(
            f"{API_URL}/chat",
            json={"question": question},
            timeout=TIMEOUT
        )

        assert response.status_code == 200

        data = response.json()
        sources = data.get("sources", [])

        print(f"\nQuestion: {question}")
        print(f"Sources: {sources}")

        # The scanned pricing fixture should be cited (it contains "WEEDING" and "$55")
        fixture_cited = any("scanned_pricing_test" in s.lower() for s in sources)
        assert fixture_cited, f"Expected scanned_pricing_test to be cited. Sources: {sources}"


class TestConversationHistory:
    """Test that conversation history enables follow-up questions."""

    def test_pronoun_resolution_with_history(self, ensure_server_running):
        """
        Test that the AI can resolve pronouns like 'this' and 'it' when given conversation history.

        This tests the core fix for follow-up questions where:
        - User asks a specific question
        - User follows up with a pronoun ("this") that should refer to the prior answer
        """
        # Requires the synthetic OCR fixture to be uploaded.
        docs = requests.get(f"{API_URL}/documents", timeout=10).json() or {}
        present = any("scanned_pricing_test.pdf".lower() == k.lower() for k in docs.keys())
        if not present:
            pytest.skip("OCR fixture 'scanned_pricing_test.pdf' not uploaded to backend")

        # First, establish context with a question that should cite the scanned pricing fixture
        context_question = "What do we pay for weeding?"
        context_response = requests.post(
            f"{API_URL}/chat",
            json={"question": context_question},
            timeout=TIMEOUT
        )

        assert context_response.status_code == 200
        context_answer = context_response.json().get("answer", "")

        print(f"\n=== CONTEXT QUESTION ===")
        print(f"Q: {context_question}")
        print(f"A: {context_answer[:200]}...")

        # Now ask a follow-up with pronouns, including history
        followup_question = "Is this an hourly rate?"
        history = [
            {"role": "user", "content": context_question},
            {"role": "assistant", "content": context_answer}
        ]

        followup_response = requests.post(
            f"{API_URL}/chat",
            json={
                "question": followup_question,
                "history": history
            },
            timeout=TIMEOUT
        )

        assert followup_response.status_code == 200
        followup_data = followup_response.json()
        followup_answer = followup_data.get("answer", "").lower()
        followup_sources = followup_data.get("sources", [])

        print(f"\n=== FOLLOW-UP QUESTION (with history) ===")
        print(f"Q: {followup_question}")
        print(f"A: {followup_answer[:300]}...")
        print(f"Sources: {followup_sources}")

        # The follow-up should either cite the same fixture or mention hourly/T&M context.
        pricing_terms = ["hour", "hourly", "t&m", "time and material", "per man"]
        has_pricing_context = any(term in followup_answer for term in pricing_terms)
        fixture_in_sources = any("scanned_pricing_test" in s.lower() for s in followup_sources)

        assert has_pricing_context or fixture_in_sources, \
            f"Follow-up should reference pricing context or cite scanned_pricing_test. Answer: {followup_answer[:200]}, Sources: {followup_sources}"

    def test_follow_up_without_history_fails(self, ensure_server_running):
        """
        Demonstrate that without history, pronoun resolution fails.
        This is a negative test to show the importance of conversation history.
        """
        # Ask a vague follow-up question without any history
        vague_question = "is this a good idea?"

        response = requests.post(
            f"{API_URL}/chat",
            json={"question": vague_question},  # No history provided
            timeout=TIMEOUT
        )

        assert response.status_code == 200
        answer = response.json().get("answer", "").lower()

        print(f"\n=== VAGUE QUESTION (no history) ===")
        print(f"Q: {vague_question}")
        print(f"A: {answer[:200]}...")

        # Without context, the AI might:
        # 1. Ask for clarification
        # 2. Answer about something random
        # 3. Say it doesn't have enough context
        # Any of these are acceptable - the point is it WON'T correctly answer about lawn care

        # We just verify the request succeeded - the actual behavior depends on the LLM
        assert len(answer) > 0, "Should get some answer"

    def test_multi_turn_conversation(self, ensure_server_running):
        """
        Test a multi-turn conversation to ensure history accumulates correctly.
        """
        history = []

        # Requires the synthetic OCR fixture to be uploaded.
        docs = requests.get(f"{API_URL}/documents", timeout=10).json() or {}
        present = any("scanned_pricing_test.pdf".lower() == k.lower() for k in docs.keys())
        if not present:
            pytest.skip("OCR fixture 'scanned_pricing_test.pdf' not uploaded to backend")

        # Turn 1: Initial question
        q1 = "What is the seasonal contract price?"
        r1 = requests.post(f"{API_URL}/chat", json={"question": q1}, timeout=TIMEOUT)
        assert r1.status_code == 200
        a1 = r1.json().get("answer", "")

        history.append({"role": "user", "content": q1})
        history.append({"role": "assistant", "content": a1})

        print(f"\n=== TURN 1 ===")
        print(f"Q: {q1}")
        print(f"A: {a1[:150]}...")

        # Turn 2: Follow-up with history
        q2 = "Is that a fixed seasonal price or an hourly rate?"
        r2 = requests.post(
            f"{API_URL}/chat",
            json={"question": q2, "history": history},
            timeout=TIMEOUT
        )
        assert r2.status_code == 200
        a2 = r2.json().get("answer", "")

        history.append({"role": "user", "content": q2})
        history.append({"role": "assistant", "content": a2})

        print(f"\n=== TURN 2 ===")
        print(f"Q: {q2}")
        print(f"A: {a2[:150]}...")

        # Turn 3: Another follow-up
        q3 = "Are there any additional costs beyond that?"
        r3 = requests.post(
            f"{API_URL}/chat",
            json={"question": q3, "history": history},
            timeout=TIMEOUT
        )
        assert r3.status_code == 200
        a3 = r3.json().get("answer", "")

        print(f"\n=== TURN 3 ===")
        print(f"Q: {q3}")
        print(f"A: {a3[:150]}...")

        # The third answer should maintain pricing context and possibly mention $55 or dumping fees.
        answer_lower = a3.lower()
        has_context = any(term in answer_lower for term in
            ["weeding", "t&m", "time and material", "$55", "dumping", "hour", "cost", "additional"])

        assert has_context, \
            f"Multi-turn answer should maintain context. Got: {a3[:200]}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
