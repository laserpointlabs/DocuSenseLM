"""
OpenAI API client
"""
import os
from typing import List, Optional
from openai import AsyncOpenAI
from .llm_client import LLMClient, Chunk, Citation, Answer
from .prompts import (
    build_system_prompt, 
    build_user_prompt, 
    build_cross_document_prompt,
    build_conversational_system_prompt,
    build_conversational_prompt,
    detect_question_type,
    is_conversational_question
)


class OpenAIClient(LLMClient):
    """OpenAI API client"""

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize OpenAI client

        Args:
            api_key: OpenAI API key (default from env)
            model: Model name (must be provided or set via OPENAI_MODEL env var)
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model or os.getenv("OPENAI_MODEL")
        if not self.model:
            raise ValueError("OPENAI_MODEL environment variable must be set")

    async def generate_answer(
        self,
        query: str,
        context_chunks: List[Chunk],
        citations: List[Citation],
        use_conversational: bool = False,
        additional_info: str = ""
    ) -> Answer:
        """
        Generate answer using OpenAI
        
        Args:
            query: User question
            context_chunks: Retrieved document chunks
            citations: Citation information
            use_conversational: Whether to use conversational mode (auto-detected if False)
            additional_info: Optional additional information (e.g., calculated days/months)
        """

        # Use centralized prompts from prompts.py
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"=== OpenAI Answer Generation ===")
        logger.info(f"Query: {query}")
        logger.info(f"Number of context chunks: {len(context_chunks)}")
        logger.info(f"Number of citations: {len(citations)}")

        # Auto-detect conversational questions if not explicitly set
        if not use_conversational:
            use_conversational = is_conversational_question(query)
        
        logger.info(f"Using {'conversational' if use_conversational else 'structured'} mode")

        # Log each chunk individually
        if context_chunks:
            logger.info(f"=== Context Chunks Details ===")
            for i, chunk in enumerate(context_chunks[:5]):  # Log first 5 chunks
                logger.info(f"Chunk {i+1}: doc_id={chunk.doc_id[:8]}..., clause={chunk.clause_number}, page={chunk.page_num}, text_length={len(chunk.text)}")
                logger.info(f"  Text preview: {chunk.text[:200]}...")
            if len(context_chunks) > 5:
                logger.info(f"... and {len(context_chunks) - 5} more chunks")
            logger.info(f"=== End Context Chunks ===")
        else:
            logger.warning("⚠️  NO CONTEXT CHUNKS PROVIDED!")

        # Build prompts based on mode
        if use_conversational:
            # Use conversational prompts
            system_prompt = build_conversational_system_prompt()
            question_type = detect_question_type(query)
            if question_type == "cross_document":
                user_prompt = build_cross_document_prompt(query, context_chunks, citations)
            else:
                user_prompt = build_conversational_prompt(query, context_chunks, citations, additional_info)
        else:
            # Use structured prompts
            question_type = detect_question_type(query)
            logger.info(f"Detected question type: {question_type}")
            
            system_prompt = build_system_prompt()
            
            if question_type == "cross_document":
                user_prompt = build_cross_document_prompt(query, context_chunks, citations)
            else:
                user_prompt = build_user_prompt(query, context_chunks, citations)
        
        logger.info(f"=== System Prompt ===")
        logger.info(f"{system_prompt[:500]}...")  # Log first 500 chars
        logger.info(f"=== End System Prompt ===")

        logger.info(f"=== User Prompt ===")
        logger.info(f"{user_prompt[:500]}...")  # Log first 500 chars
        logger.info(f"=== End User Prompt ===")

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            answer_text = response.choices[0].message.content

            logger.info(f"=== LLM Response ===")
            logger.info(f"Raw LLM answer: {answer_text}")
            logger.info(f"Answer length: {len(answer_text)} characters")
            logger.info(f"=== End LLM Response ===")

            return Answer(
                text=answer_text,
                citations=citations
            )
        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")

    async def generate_question_suggestions(
        self,
        document_text: str,
        category: Optional[str] = None
    ) -> List[str]:
        """Generate question suggestions using OpenAI"""

        category_hint = f"Focus on {category}." if category else ""

        system_prompt = """You are analyzing NDA documents. Generate relevant questions that help understand key terms and obligations."""

        user_prompt = f"""Generate 5-10 relevant questions about this NDA document excerpt.

{category_hint}

Document excerpt:
{document_text[:2000]}

Generate specific, answerable questions about:
- Confidentiality scope and definitions
- Obligations and restrictions
- Exceptions to confidentiality
- Term and survival periods
- Governing law and jurisdiction
- Mutual vs unilateral obligations

Format as a numbered list."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )

            text = response.choices[0].message.content

            # Parse numbered list
            questions = []
            for line in text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    question = line.split('.', 1)[-1].strip()
                    if question.startswith('-'):
                        question = question[1:].strip()
                    if question and len(question) > 10:
                        questions.append(question)

            return questions[:10]
        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")
