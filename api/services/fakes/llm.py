from __future__ import annotations

from typing import List, Optional

from llm.llm_client import LLMClient, Chunk, Citation, Answer


class EchoLLMClient(LLMClient):
    """
    Deterministic LLM client for tests.
    Returns responses that echo the query and summarize provided context.
    """

    async def generate_answer(
        self,
        query: str,
        context_chunks: List[Chunk],
        citations: List[Citation]
    ) -> Answer:
        excerpt_summary = " | ".join(chunk.text[:50] for chunk in context_chunks[:3])
        text = f"[FAKE ANSWER] {query}\nContext: {excerpt_summary}"
        return Answer(text=text, citations=citations)

    async def generate_question_suggestions(
        self,
        document_text: str,
        category: Optional[str] = None
    ) -> List[str]:
        base = category or "General"
        return [f"{base} question about: {document_text[:60]}"]
