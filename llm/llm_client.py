"""
Abstract base class for LLM clients
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Chunk:
    """Text chunk with metadata"""
    text: str
    doc_id: str
    clause_number: Optional[str]
    page_num: int
    span_start: int
    span_end: int
    source_uri: str


@dataclass
class Citation:
    """Citation for an answer"""
    doc_id: str
    clause_number: Optional[str]
    page_num: int
    span_start: int
    span_end: int
    source_uri: str
    excerpt: str


@dataclass
class Answer:
    """LLM-generated answer with citations"""
    text: str
    citations: List[Citation]
    confidence: Optional[float] = None  # Confidence score (0.0 to 1.0)
    evaluation_reasoning: Optional[str] = None  # Optional reasoning for confidence score


class LLMClient(ABC):
    """Abstract base class for LLM clients"""

    @abstractmethod
    async def generate_answer(
        self,
        query: str,
        context_chunks: List[Chunk],
        citations: List[Citation],
        use_conversational: bool = False,
        additional_info: str = ""
    ) -> Answer:
        """
        Generate an answer from query and context

        Args:
            query: User question
            context_chunks: Retrieved context chunks
            citations: Citation information
            use_conversational: Whether to use conversational mode (auto-detected if False)
            additional_info: Optional additional information (e.g., calculated days/months)

        Returns:
            Answer with text and citations
        """
        pass

    @abstractmethod
    async def generate_question_suggestions(
        self,
        document_text: str,
        category: Optional[str] = None
    ) -> List[str]:
        """
        Generate question suggestions based on document content

        Args:
            document_text: Document text to analyze
            category: Optional category for questions

        Returns:
            List of suggested questions
        """
        pass
