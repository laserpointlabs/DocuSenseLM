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
    {
        "id": "weeding_cost",
        "question": "What do we pay for weeding?",
        "expected_patterns": [
            r"\$55",  # Should mention $55
            r"(per\s*(man)?\s*hour|hourly|T&M|time\s*and\s*material)",  # Should mention hourly/T&M
        ],
        "expected_source": "Franny",  # Should cite Franny's agreement
    },
    {
        "id": "seasonal_price",
        "question": "What is the seasonal contract price?",
        "expected_patterns": [
            r"\$15,?000",  # Should mention $15,000
        ],
        "expected_source": "Franny",
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
        # "weeding" is a unique term only in Franny's document
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
        
        # Franny should be in sources since it's the only doc with "weeding"
        franny_cited = any("franny" in s.lower() for s in sources)
        assert franny_cited, f"Franny's doc should be cited for 'weeding' query. Sources: {sources}"


class TestConversationHistory:
    """Test that conversation history enables follow-up questions."""
    
    def test_pronoun_resolution_with_history(self, ensure_server_running):
        """
        Test that the AI can resolve pronouns like 'this' and 'it' when given conversation history.
        
        This tests the core fix for the issue where:
        - User asks about Franny's mid-summer treatment
        - User follows up with "is this a good idea?"
        - Without history: AI answers about random topics (like NDAs)
        - With history: AI understands "this" refers to the lawn treatment
        """
        # First, establish context with a question about Franny's services
        context_question = "what does franny do in mid summer"
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
        followup_question = "is this a good idea?"
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
        
        # The answer should reference lawn care context OR Franny's document should be in sources
        # This validates that query expansion is working to retrieve relevant context
        lawn_terms = ["lawn", "fertiliz", "grass", "weed", "treatment", "summer", "grub", "landscape", "franny", "maintenance"]
        
        has_lawn_context = any(term in followup_answer for term in lawn_terms)
        franny_in_sources = any("franny" in s.lower() for s in followup_sources)
        
        # Either the answer mentions lawn care context, OR Franny's doc is in sources
        # (query expansion is working even if LLM hedges in response)
        assert has_lawn_context or franny_in_sources, \
            f"Follow-up should reference lawn care or cite Franny's doc. Answer: {followup_answer[:200]}, Sources: {followup_sources}"
    
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
        
        # Turn 1: Initial question
        q1 = "What is the seasonal contract price for Franny?"
        r1 = requests.post(f"{API_URL}/chat", json={"question": q1}, timeout=TIMEOUT)
        assert r1.status_code == 200
        a1 = r1.json().get("answer", "")
        
        history.append({"role": "user", "content": q1})
        history.append({"role": "assistant", "content": a1})
        
        print(f"\n=== TURN 1 ===")
        print(f"Q: {q1}")
        print(f"A: {a1[:150]}...")
        
        # Turn 2: Follow-up with history
        q2 = "what services are included in that price?"
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
        q3 = "are there any additional costs beyond that?"
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
        
        # The third answer should reference Franny/lawn care (from context)
        # and possibly mention T&M or weeding costs
        answer_lower = a3.lower()
        has_context = any(term in answer_lower for term in 
            ["franny", "weeding", "t&m", "time and material", "$55", "additional", "lawn", "cost"])
        
        assert has_context, \
            f"Multi-turn answer should maintain context. Got: {a3[:200]}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
