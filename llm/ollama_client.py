"""
Ollama LLM client (local or network)
"""
import os
import httpx
from typing import List, Dict, Optional
from .llm_client import LLMClient, Chunk, Citation, Answer


class OllamaClient(LLMClient):
    """Ollama API client"""

    def __init__(self, endpoint: str = None, model: str = None):
        """
        Initialize Ollama client

        Args:
            endpoint: Ollama API endpoint (default from env)
            model: Model name to use (default from env or "llama2")
        """
        self.endpoint = endpoint or os.getenv("LLM_ENDPOINT", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama2")
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate_answer(
        self,
        query: str,
        context_chunks: List[Chunk],
        citations: List[Citation]
    ) -> Answer:
        """Generate answer using Ollama"""

        # Build context from chunks
        context_text = "\n\n".join([
            f"[Document {chunk.doc_id}, Clause {chunk.clause_number}, Page {chunk.page_num}]\n{chunk.text}"
            for chunk in context_chunks
        ])

        # Log context for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== Ollama Answer Generation ===")
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

        # Build prompt with explicit format examples
        prompt = f"""You are an expert legal assistant analyzing Non-Disclosure Agreements (NDAs).

Based on the following context from NDA documents, answer the user's question. Your answer will be displayed directly to users in the Ask Question tab, so provide clear, concise responses.

CRITICAL FORMAT RULES - Return answers EXACTLY like these examples:

For DATE questions:
  Question: "What is the effective date of the NDA?"
  CORRECT Answer: "September 5, 2025"
  WRONG Answer: "The effective date of the NDA is September 5, 2025. This date was specified in the agreement..."

For DURATION/TERM questions:
  Question: "What is the term of the NDA?"
  CORRECT Answer: "3 years"
  Alternative: "36 months"
  WRONG Answer: "The term is three years from the effective date..."

For GOVERNING LAW questions:
  Question: "What is the governing law for the NDA?"
  CORRECT Answer: "State of Delaware"
  WRONG Answer: "The governing law clause specifies that the laws of the State of Delaware apply..."

For MUTUAL/UNILATERAL questions:
  Question: "Is the NDA mutual or unilateral?"
  CORRECT Answer: "mutual"
  WRONG Answer: "This is a mutual agreement, meaning both parties have obligations..."

For PARTY NAME questions:
  Question: "Who are the parties to the NDA?"
  CORRECT Answer: "Norris Cylinder Company and Acme Corporation"
  WRONG Answer: "The parties include Norris Cylinder Company and Acme Corporation as mentioned in..."

For GENERAL questions (if not covered above):
  Provide a brief, direct answer (1-2 sentences maximum). Do NOT repeat the question or add unnecessary context.

Context from NDA documents:
{context_text}

User Question: {query}

IMPORTANT: Only use information from the context provided above. If the context does not contain the answer, respond with "I cannot find this information in the provided documents".

Return your answer in the format shown in the examples above. Answer ONLY (no explanations, no context, no additional text):"""

        try:
            response = await self.client.post(
                f"{self.endpoint}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()

            answer_text = result.get("response", "")

            logger.info(f"=== LLM Response ===")
            logger.info(f"Raw LLM answer: {answer_text}")
            logger.info(f"Answer length: {len(answer_text)} characters")
            logger.info(f"=== End LLM Response ===")

            return Answer(
                text=answer_text,
                citations=citations
            )
        except Exception as e:
            raise Exception(f"Ollama API error: {e}")

    async def generate_question_suggestions(
        self,
        document_text: str,
        category: Optional[str] = None
    ) -> List[str]:
        """Generate question suggestions using Ollama"""

        category_hint = f"Focus on {category}." if category else ""

        prompt = f"""You are analyzing an NDA document. Generate 5-10 relevant questions that would help understand the key terms and obligations in this document.

{category_hint}

Document excerpt:
{document_text[:2000]}...

Generate specific, answerable questions about:
- Confidentiality scope and definitions
- Obligations and restrictions
- Exceptions to confidentiality
- Term and survival periods
- Governing law and jurisdiction
- Mutual vs unilateral obligations

Format as a numbered list of questions."""

        try:
            response = await self.client.post(
                f"{self.endpoint}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()

            text = result.get("response", "")
            # Parse numbered list
            questions = []
            for line in text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    # Remove numbering/bullets
                    question = line.split('.', 1)[-1].strip()
                    if question.startswith('-'):
                        question = question[1:].strip()
                    if question and len(question) > 10:
                        questions.append(question)

            return questions[:10]  # Return up to 10 questions
        except Exception as e:
            raise Exception(f"Ollama API error: {e}")

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
