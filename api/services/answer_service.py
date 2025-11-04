"""
Answer service for LLM-generated answers with citations
"""
from typing import List, Dict, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from llm.llm_factory import get_llm_client
from llm.llm_client import Chunk, Citation, Answer
from api.services.search_service import search_service


class AnswerService:
    """Service for generating answers with citations"""

    def __init__(self):
        self.search = search_service
        self.llm_client = None  # Lazy load

    async def generate_answer(
        self,
        question: str,
        filters: Optional[Dict] = None,
        max_context_chunks: int = 10
    ) -> Answer:
        """
        Generate answer using hybrid search + LLM

        Args:
            question: User question
            filters: Optional filters
            max_context_chunks: Maximum chunks to use as context

        Returns:
            Answer with citations
        """
        # 1. Run hybrid search
        search_results = self.search.hybrid_search(
            query=question,
            k=max_context_chunks * 2,  # Get more results for better context
            filters=filters
        )

        # 2. Take top chunks
        top_chunks = search_results[:max_context_chunks]

        # 3. Convert to Chunk objects
        context_chunks = self.search.get_chunks_for_answer(top_chunks)

        # 4. Build citations
        citations = []
        for result in top_chunks:
            citation = Citation(
                doc_id=result['doc_id'],
                clause_number=result.get('clause_number'),
                page_num=result['page_num'],
                span_start=result['span_start'],
                span_end=result['span_end'],
                source_uri=result['source_uri'],
                excerpt=result['text'][:200] + "..." if len(result['text']) > 200 else result['text']
            )
            citations.append(citation)

        # 5. Call LLM
        if self.llm_client is None:
            self.llm_client = get_llm_client()

        answer = await self.llm_client.generate_answer(
            query=question,
            context_chunks=context_chunks,
            citations=citations
        )

        return answer


# Global service instance
answer_service = AnswerService()
