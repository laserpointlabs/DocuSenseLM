"""
Unit tests for hybrid search functions.
These tests don't require OpenAI API or ChromaDB - they test the pure logic.
"""
import pytest
import sys
import os

# Add python folder to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))

# Import the functions we want to test
# We need to mock some things since server.py has side effects on import
from unittest.mock import patch, MagicMock

# Mock chromadb and openai before importing server
with patch.dict('sys.modules', {
    'chromadb': MagicMock(),
    'chromadb.utils': MagicMock(),
    'chromadb.utils.embedding_functions': MagicMock(),
}):
    # Set required env vars
    os.environ.setdefault('OPENAI_API_KEY', 'test-key')
    os.environ.setdefault('USER_DATA_DIR', '/tmp/test_docusenselm')
    
    # Now we can import the helper functions
    from server import extract_keywords, keyword_search, STOP_WORDS


class TestExtractKeywords:
    """Test the keyword extraction function."""
    
    def test_basic_extraction(self):
        """Test basic keyword extraction from a simple query."""
        query = "What do we pay for weeding?"
        keywords = extract_keywords(query)
        
        assert "weeding" in keywords
        assert "pay" in keywords
        # Stop words should be filtered
        assert "what" not in keywords
        assert "do" not in keywords
        assert "we" not in keywords
        assert "for" not in keywords
    
    def test_filters_short_words(self):
        """Words with 2 or fewer chars should be filtered."""
        query = "I am at a test"
        keywords = extract_keywords(query)
        
        # All words are either stop words or <= 2 chars
        assert "test" in keywords
        assert len(keywords) == 1
    
    def test_stop_words_filtered(self):
        """Stop words should not appear in results."""
        query = "the quick brown fox jumps over lazy dog"
        keywords = extract_keywords(query)
        
        assert "the" not in keywords
        assert "over" not in keywords
        assert "quick" in keywords
        assert "brown" in keywords
        assert "jumps" in keywords
        assert "lazy" in keywords
    
    def test_case_insensitive(self):
        """Keywords should be lowercase."""
        query = "WEEDING costs PRICE"
        keywords = extract_keywords(query)
        
        assert "weeding" in keywords
        assert "costs" in keywords
        assert "price" in keywords
        assert "WEEDING" not in keywords
    
    def test_empty_query(self):
        """Empty query should return empty list."""
        keywords = extract_keywords("")
        assert keywords == []
    
    def test_only_stop_words(self):
        """Query with only stop words should return empty list."""
        query = "the and or but"
        keywords = extract_keywords(query)
        assert keywords == []
    
    def test_pricing_query_keywords(self):
        """Test extraction from a typical pricing query."""
        query = "What is the hourly rate for landscaping services?"
        keywords = extract_keywords(query)
        
        assert "hourly" in keywords
        assert "rate" in keywords
        assert "landscaping" in keywords
        assert "services" in keywords


class TestKeywordSearch:
    """Test the keyword-based search function."""
    
    @pytest.fixture
    def sample_chunks(self):
        """Sample chunks for testing."""
        return [
            {
                'id': 'chunk1',
                'doc': 'WEEDING: Weed out beds, curbs, walkways. T&M @ $55.00 per man hour.',
                'metadata': {'filename': 'franny_maintenance.pdf'}
            },
            {
                'id': 'chunk2', 
                'doc': 'Seasonal lawn care includes fertilization and broadleaf weed control.',
                'metadata': {'filename': 'franny_maintenance.pdf'}
            },
            {
                'id': 'chunk3',
                'doc': 'Non-disclosure agreement between Party A and Party B.',
                'metadata': {'filename': 'nda.pdf'}
            },
            {
                'id': 'chunk4',
                'doc': 'The payment terms are net 30 days. Pay invoices promptly.',
                'metadata': {'filename': 'contract.pdf'}
            },
        ]
    
    def test_finds_matching_chunks(self, sample_chunks):
        """Should find chunks containing query keywords."""
        results = keyword_search("weeding", sample_chunks, n_results=10)
        
        assert len(results) > 0
        # First result should be the chunk with "WEEDING"
        assert 'weeding' in results[0]['doc'].lower()
    
    def test_ranks_by_keyword_score(self, sample_chunks):
        """Chunks with more keyword matches should rank higher."""
        results = keyword_search("weeding beds curbs", sample_chunks, n_results=10)
        
        assert len(results) > 0
        # Chunk1 has "weeding", "beds", "curbs" - should be first
        assert results[0]['id'] == 'chunk1'
    
    def test_no_matches_returns_empty(self, sample_chunks):
        """Query with no matching keywords returns empty list."""
        results = keyword_search("xyznonexistent", sample_chunks, n_results=10)
        assert results == []
    
    def test_respects_n_results_limit(self, sample_chunks):
        """Should not return more than n_results."""
        results = keyword_search("the", sample_chunks, n_results=2)
        assert len(results) <= 2
    
    def test_adds_keyword_score(self, sample_chunks):
        """Results should have keyword_score field."""
        results = keyword_search("weeding", sample_chunks, n_results=10)
        
        for result in results:
            assert 'keyword_score' in result
            assert result['keyword_score'] > 0
    
    def test_adds_matched_keywords(self, sample_chunks):
        """Results should have matched_keywords field."""
        results = keyword_search("weeding", sample_chunks, n_results=10)
        
        for result in results:
            assert 'matched_keywords' in result
            assert isinstance(result['matched_keywords'], list)
    
    def test_multiple_keyword_bonus(self, sample_chunks):
        """Chunks matching multiple keywords should get bonus score."""
        # Search with multiple keywords
        results = keyword_search("weeding beds walkways", sample_chunks, n_results=10)
        
        if len(results) > 0:
            # Chunk1 matches all three keywords
            chunk1_result = next((r for r in results if r['id'] == 'chunk1'), None)
            if chunk1_result:
                assert len(chunk1_result['matched_keywords']) >= 2


class TestStopWords:
    """Test the stop words set."""
    
    def test_common_stop_words_present(self):
        """Common English stop words should be in the set."""
        common = ['the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were']
        for word in common:
            assert word in STOP_WORDS, f"'{word}' should be a stop word"
    
    def test_question_words_present(self):
        """Question words should be filtered."""
        question_words = ['what', 'which', 'who', 'where', 'when', 'why', 'how']
        for word in question_words:
            assert word in STOP_WORDS, f"'{word}' should be a stop word"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
