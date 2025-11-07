import asyncio

import pytest

from api.services.answer_service import AnswerService
from api.services.service_registry import (
    override_search_service,
    reset_search_service,
)
from llm.llm_client import Chunk, Citation, Answer


class FakeSearchService:
    def __init__(self, results):
        self._results = results

    def hybrid_search(self, query, k=50, filters=None):
        return self._results

    def get_chunks_for_answer(self, results):
        chunks = []
        for res in results:
            chunks.append(
                Chunk(
                    text=res.get("text", ""),
                    doc_id=res.get("doc_id", ""),
                    clause_number=res.get("clause_number"),
                    page_num=res.get("page_num", 0),
                    span_start=res.get("span_start", 0),
                    span_end=res.get("span_end", 0),
                    source_uri=res.get("source_uri", ""),
                )
            )
        return chunks


class FakeLLMClient:
    def __init__(self):
        self.last_query = None
        self.last_context = None

    async def generate_answer(self, query, context_chunks, citations):
        self.last_query = query
        self.last_context = context_chunks
        return Answer(text=f"Answer for: {query}", citations=citations)

    async def generate_question_suggestions(self, document_text, category=None):
        return []


@pytest.fixture
def override_answer_dependencies():
    answers = {
        "doc-1": {
            "text": "The effective date is January 15, 2024.",
            "clause_number": "1",
            "page_num": 1,
        }
    }

    results = [
        {
            "chunk_id": "chunk-1",
            "doc_id": "doc-1",
            "text": answers["doc-1"]["text"],
            "clause_number": "1",
            "page_num": 1,
            "span_start": 0,
            "span_end": 40,
            "source_uri": "s3://nda/doc1.pdf",
            "score": 0.9,
        },
        {
            "chunk_id": "chunk-1-dup",
            "doc_id": "doc-1",
            "text": answers["doc-1"]["text"],
            "clause_number": "1",
            "page_num": 1,
            "span_start": 0,
            "span_end": 40,
            "source_uri": "s3://nda/doc1.pdf",
            "score": 0.8,
        },
    ]

    fake_search = FakeSearchService(results)
    fake_llm = FakeLLMClient()

    override_search_service(fake_search)

    try:
        yield fake_llm
    finally:
        reset_search_service()


@pytest.fixture
def fake_llm(monkeypatch):
    client = FakeLLMClient()
    monkeypatch.setattr("api.services.answer_service.get_llm_client", lambda: client)
    return client


def test_answer_service_deduplicates_citations(override_answer_dependencies, fake_llm):
    service = AnswerService()

    answer = asyncio.run(
        service.generate_answer(
            question="What is the effective date?",
            max_context_chunks=5,
        )
    )

    assert answer.text.startswith("Answer for:")
    # Only one citation after deduplication
    assert len(answer.citations) == 1
    citation = answer.citations[0]
    assert citation.doc_id == "doc-1"
    assert citation.page_num == 1


def test_answer_service_structured_extraction(override_answer_dependencies, fake_llm):
    service = AnswerService()

    answer = asyncio.run(
        service.generate_answer(
            question="What is the effective date?",
            max_context_chunks=5,
        )
    )

    assert "Answer for" in answer.text

    assert fake_llm.last_query == "What is the effective date?"
    assert len(fake_llm.last_context) == 1
