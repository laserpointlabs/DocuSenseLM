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

        # Build prompt
        prompt = f"""You are an expert legal assistant analyzing Non-Disclosure Agreements (NDAs).

Based on the following context from NDA documents, answer the user's question. Provide accurate, specific answers with references to the relevant clauses.

Context:
{context_text}

User Question: {query}

Answer the question based on the context provided. Be specific and cite the relevant clauses when possible."""

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
