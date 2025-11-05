"""
OpenAI API client
"""
import os
from typing import List, Optional
from openai import AsyncOpenAI
from .llm_client import LLMClient, Chunk, Citation, Answer


class OpenAIClient(LLMClient):
    """OpenAI API client"""

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize OpenAI client

        Args:
            api_key: OpenAI API key (default from env)
            model: Model name (default "gpt-3.5-turbo")
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    async def generate_answer(
        self,
        query: str,
        context_chunks: List[Chunk],
        citations: List[Citation]
    ) -> Answer:
        """Generate answer using OpenAI"""

        # Build context from chunks
        context_text = "\n\n".join([
            f"[Document {chunk.doc_id}, Clause {chunk.clause_number}, Page {chunk.page_num}]\n{chunk.text}"
            for chunk in context_chunks
        ])

        # Log context for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== OpenAI Answer Generation ===")
        logger.info(f"Query: {query}")
        logger.info(f"Number of context chunks: {len(context_chunks)}")
        logger.info(f"Context text length: {len(context_text)} characters")
        logger.info(f"Number of citations: {len(citations)}")

        # Log each chunk individually
        if context_chunks:
            logger.info(f"=== Context Chunks Details ===")
            for i, chunk in enumerate(context_chunks):
                logger.info(f"Chunk {i+1}: doc_id={chunk.doc_id[:8]}..., clause={chunk.clause_number}, page={chunk.page_num}, text_length={len(chunk.text)}")
                logger.info(f"  Chunk {i+1} text (full): {chunk.text}")
        else:
            logger.warning("⚠️  NO CONTEXT CHUNKS PROVIDED!")

        logger.info(f"=== Full Context Text (for prompt) ===")
        logger.info(f"Context text length: {len(context_text)} characters")
        logger.info(f"Context text:\n{context_text}")
        logger.info(f"=== End Context Text ===")

        # Also log the user prompt that will be sent
        user_prompt = f"""Based on the following context from NDA documents, answer this question:

{context_text}

Question: {query}

IMPORTANT: Only use information from the context provided above. If the context does not contain the answer, respond with "I cannot find this information in the provided documents".

Return your answer in the format shown in the system instructions. Answer ONLY (no explanations, no context, no additional text):"""

        logger.info(f"=== User Prompt (what LLM will see) ===")
        logger.info(f"{user_prompt}")
        logger.info(f"=== End User Prompt ===")

        system_prompt = """You are an expert legal assistant analyzing Non-Disclosure Agreements (NDAs).
Your answers will be displayed directly to users in the Ask Question tab. Provide clear, concise responses in the exact formats specified below.

CRITICAL FORMAT RULES - Return answers EXACTLY like these examples:

For DATE questions:
  Question: "What is the effective date of the NDA?"
  CORRECT Answer: "September 5, 2025"
  WRONG Answer: "The effective date of the NDA is September 5, 2025. This date was specified..."

For DURATION/TERM questions:
  Question: "What is the term of the NDA?"
  CORRECT Answer: "3 years" or "36 months"
  WRONG Answer: "The term is three years from the effective date..."

For GOVERNING LAW questions:
  Question: "What is the governing law for the NDA?"
  CORRECT Answer: "State of Delaware"
  WRONG Answer: "The governing law clause specifies that the laws of the State of Delaware..."

For MUTUAL/UNILATERAL questions:
  Question: "Is the NDA mutual or unilateral?"
  CORRECT Answer: "mutual"
  WRONG Answer: "This is a mutual agreement, meaning both parties..."

For PARTY NAME questions:
  Question: "Who are the parties to the NDA?"
  CORRECT Answer: "Norris Cylinder Company and Acme Corporation"
  WRONG Answer: "The parties include Norris Cylinder Company and Acme Corporation as mentioned..."

For GENERAL questions (if not covered above):
  Provide a brief, direct answer (1-2 sentences maximum). Do NOT repeat the question or add unnecessary context.

CRITICAL: If the context provided does NOT contain the information needed to answer the question, you MUST respond with "I cannot find this information in the provided documents" or "This information is not available in the provided context". Do NOT make up or guess answers."""

        user_prompt = f"""Based on the following context from NDA documents, answer this question:

{context_text}

Question: {query}

IMPORTANT: Only use information from the context provided above. If the context does not contain the answer, respond with "I cannot find this information in the provided documents".

Return your answer in the format shown in the system instructions. Answer ONLY (no explanations, no context, no additional text):"""

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
