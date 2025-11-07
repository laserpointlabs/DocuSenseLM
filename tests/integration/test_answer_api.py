import asyncio

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.service_registry import (
    override_search_service,
    reset_search_service,
)
from llm.llm_client import Chunk, Answer, Citation


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
        self.calls = []

    async def generate_answer(self, query, context_chunks, citations):
        self.calls.append((query, context_chunks))
        return Answer(text=f"[Stubbed Answer] {query}", citations=citations)

    async def generate_question_suggestions(self, document_text, category=None):
        return []


@pytest.fixture
def override_answer_services(monkeypatch):
    results = [
        {
            "chunk_id": "chunk-1",
            "doc_id": "doc-123",
            "text": "The governing law is the State of Delaware.",
            "section_type": "clause",
            "clause_number": "4",
            "page_num": 2,
            "span_start": 0,
            "span_end": 50,
            "source_uri": "s3://nda/doc-123.pdf",
            "score": 0.9,
        },
        {
            "chunk_id": "chunk-1-dup",
            "doc_id": "doc-123",
            "text": "The governing law is the State of Delaware.",
            "section_type": "clause",
            "clause_number": "4",
            "page_num": 2,
            "span_start": 0,
            "span_end": 50,
            "source_uri": "s3://nda/doc-123.pdf",
            "score": 0.8,
        },
    ]

    search = FakeSearchService(results)
    llm = FakeLLMClient()

    override_search_service(search)
    monkeypatch.setattr("api.services.answer_service.get_llm_client", lambda: llm)

    try:
        yield llm
    finally:
        reset_search_service()


def test_answer_endpoint_returns_citations(override_answer_services):
    client = TestClient(app)

    payload = {
        "question": "What is the governing law?",
        "max_context_chunks": 5,
    }

    response = client.post("/answer", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["question"] == payload["question"]
    assert data["answer"].startswith("[Stubbed Answer]")

    citations = data["citations"]
    assert len(citations) == 1
    assert citations[0]["doc_id"] == "doc-123"
    assert citations[0]["page_num"] == 2

    # Ensure fake LLM was invoked once with deduplicated context
    llm_client = override_answer_services
    assert len(llm_client.calls) == 1
    _, context = llm_client.calls[0]
    assert len(context) == 1
    assert context[0].doc_id == "doc-123"
