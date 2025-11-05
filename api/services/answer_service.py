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
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== Answer Service Start ===")
        logger.info(f"Question: {question}")
        logger.info(f"max_context_chunks: {max_context_chunks}")
        logger.info(f"filters: {filters}")

        search_results = self.search.hybrid_search(
            query=question,
            k=max_context_chunks * 3,  # Get more results for better context (removed 20 limit)
            filters=filters
        )
        logger.info(f"Search returned {len(search_results)} results")
        if search_results:
            logger.info(f"First search result: doc_id={search_results[0].get('doc_id')}, score={search_results[0].get('score')}, text_length={len(search_results[0].get('text', ''))}")

        # 2. Deduplicate by doc_id + page_num + clause_number, then take top chunks
        seen_chunks = {}
        for result in search_results:
            key = (result.get('doc_id'), result.get('page_num'), result.get('clause_number'))
            # Keep the highest scoring result for each unique citation
            if key not in seen_chunks or result.get('score', 0) > seen_chunks[key].get('score', 0):
                seen_chunks[key] = result

        # Convert back to list and sort by score
        deduplicated_results = list(seen_chunks.values())
        deduplicated_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        top_chunks = deduplicated_results[:max_context_chunks]

        logger.info(f"After deduplication: {len(top_chunks)} top chunks")
        if top_chunks:
            logger.info(f"Top chunk details: doc_id={top_chunks[0].get('doc_id')}, page={top_chunks[0].get('page_num')}, clause={top_chunks[0].get('clause_number')}, has_text={bool(top_chunks[0].get('text'))}, text_length={len(top_chunks[0].get('text', ''))}")

        # 3. Convert to Chunk objects
        context_chunks = self.search.get_chunks_for_answer(top_chunks)

        # Log context chunks for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== Answer Service Context Building ===")
        logger.info(f"Question: {question}")
        logger.info(f"Number of top_chunks: {len(top_chunks)}")
        logger.info(f"Number of context_chunks: {len(context_chunks)}")
        if top_chunks:
            logger.info(f"First top_chunk: doc_id={top_chunks[0].get('doc_id')}, text_length={len(top_chunks[0].get('text', ''))}")
        if context_chunks:
            logger.info(f"First context_chunk: doc_id={context_chunks[0].doc_id}, clause={context_chunks[0].clause_number}, page={context_chunks[0].page_num}, text_length={len(context_chunks[0].text)}")

        # 4. Build citations - use ALL top chunks (not limited to 5 docs) since we deduplicated already
        citations = []
        for result in top_chunks:
            doc_id = result.get('doc_id')
            page_num = result.get('page_num', 0)
            clause_number = result.get('clause_number')
            span_start = result.get('span_start', 0)
            span_end = result.get('span_end', 0)
            source_uri = result.get('source_uri', '')

            citation = Citation(
                doc_id=doc_id or '',
                clause_number=clause_number,
                page_num=page_num if page_num is not None else 0,
                span_start=span_start if span_start is not None else 0,
                span_end=span_end if span_end is not None else 0,
                source_uri=source_uri or '',
                excerpt=result.get('text', '')  # No truncation - use full text for excerpt
            )
            citations.append(citation)

        logger.info(f"Built {len(citations)} citations from {len(top_chunks)} top chunks")
        for i, cit in enumerate(citations[:5]):
            logger.info(f"Citation {i+1}: doc_id={cit.doc_id[:8]}..., clause={cit.clause_number}, page={cit.page_num}, excerpt_length={len(cit.excerpt)}")

        # 5. Call LLM
        if self.llm_client is None:
            self.llm_client = get_llm_client()

        logger.info(f"Calling LLM with {len(context_chunks)} context chunks and {len(citations)} citations")

        answer = await self.llm_client.generate_answer(
            query=question,
            context_chunks=context_chunks,
            citations=citations
        )

        logger.info(f"LLM returned answer: length={len(answer.text)}, answer={answer.text}")

        # 6. Context Quality Summary - Easy to review
        logger.info(f"")
        logger.info(f"═══════════════════════════════════════════════════════════════")
        logger.info(f"📊 CONTEXT QUALITY SUMMARY FOR REVIEW")
        logger.info(f"═══════════════════════════════════════════════════════════════")
        logger.info(f"Question: {question}")
        logger.info(f"Number of context chunks: {len(top_chunks)}")

        if top_chunks:
            top_scores = [r.get('score', 0) for r in top_chunks[:3]]
            avg_score = sum(top_scores) / len(top_scores) if top_scores else 0
            unique_clauses = len(set(r.get('clause_number') for r in top_chunks))
            unique_docs = len(set(r.get('doc_id') for r in top_chunks))

            logger.info(f"Average top 3 scores: {avg_score:.3f}")
            logger.info(f"Unique clauses: {unique_clauses}/{len(top_chunks)}")
            logger.info(f"Unique documents: {unique_docs}/{len(top_chunks)}")

            logger.info(f"\\nTop 5 Context Chunks:")
            for i, chunk in enumerate(top_chunks[:5]):
                logger.info(f"  {i+1}. doc_id: {chunk.get('doc_id')[:8]}..., clause: {chunk.get('clause_number')}, page: {chunk.get('page_num')}, score: {chunk.get('score', 0):.3f}")
                text_preview = chunk.get('text', '')[:150].replace('\\n', ' ')
                logger.info(f"     text: {text_preview}...")

            # If all chunks are same clause and low scores, context might be irrelevant
            if unique_clauses == 1 and avg_score < 0.15:
                logger.warning(f"⚠️  WARNING: All context chunks are from same clause (clause={top_chunks[0].get('clause_number')}) with low scores (avg={avg_score:.3f}). Context may be irrelevant to question.")

        logger.info(f"═══════════════════════════════════════════════════════════════")
        logger.info(f"")

        # 7. Post-process answer to extract structured response if needed
        # Only apply extraction for specific question types to avoid corrupting general answers
        question_lower = question.lower()
        is_structured_question = any(word in question_lower for word in [
            'effective date', 'term', 'duration', 'how long', 'governing law',
            'jurisdiction', 'mutual', 'unilateral', 'parties to'
        ])

        logger.info(f"Answer before post-processing: {answer.text}")

        if is_structured_question:
            answer.text = self._extract_structured_answer(question, answer.text)
            logger.info(f"Answer after structured extraction: {answer.text}")
        else:
            # For general questions, just clean up whitespace
            answer.text = answer.text.strip() if answer.text else ""
            logger.info(f"Answer after cleanup: {answer.text}")

        return answer

    def _extract_structured_answer(self, question: str, answer_text: str) -> str:
        """
        Extract structured answer from LLM response
        Helps ensure answers match expected formats for competency testing
        """
        if not answer_text:
            return answer_text

        import re
        question_lower = question.lower()
        answer_clean = answer_text.strip()

        # For date questions, try to extract just the date
        if any(word in question_lower for word in ['date', 'effective', 'when']):
            # Look for date patterns like "September 5, 2025" or "July 16, 2025"
            date_pattern = r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})'
            match = re.search(date_pattern, answer_clean)
            if match:
                return match.group(1)

        # For duration/term questions, extract just the duration
        if any(word in question_lower for word in ['term', 'duration', 'how long', 'months', 'years']):
            # Look for patterns like "3 years" or "36 months"
            duration_pattern = r'(\d+\s+(?:years?|months?))'
            match = re.search(duration_pattern, answer_clean, re.IGNORECASE)
            if match:
                return match.group(1)

        # For governing law questions, extract just the jurisdiction
        if any(word in question_lower for word in ['governing law', 'jurisdiction', 'law applies']):
            # Look for patterns like "State of Delaware" or "State of California"
            law_pattern = r'State of ([A-Z][a-z]+)'
            match = re.search(law_pattern, answer_clean)
            if match:
                return f"State of {match.group(1)}"

        # For mutual/unilateral questions, extract just the answer
        if any(word in question_lower for word in ['mutual', 'unilateral']):
            answer_lower = answer_clean.lower()
            if 'mutual' in answer_lower and 'unilateral' not in answer_lower:
                return 'mutual'
            elif 'unilateral' in answer_lower:
                return 'unilateral'

        # For other questions, don't truncate - return the full answer
        # The LLM prompt already asks for concise answers, so trust the LLM
        return answer_clean


# Global service instance
answer_service = AnswerService()
