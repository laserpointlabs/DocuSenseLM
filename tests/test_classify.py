import asyncio
import os
import tempfile
import subprocess
from pathlib import Path

import fitz  # type: ignore
import pytest


class StubOpenAIMessage:
    def __init__(self, content: str):
        self.content = content


class StubChoice:
    def __init__(self, content: str):
        self.message = StubOpenAIMessage(content)


class StubChat:
    def __init__(self, mapping):
        self.mapping = mapping

    def completions(self, *args, **kwargs):
        return self

    def create(self, *args, **kwargs):
        # Use filename (passed in prompt) to decide type
        prompt = kwargs["messages"][1]["content"]
        chosen = "default"
        for needle, doc_type in self.mapping.items():
            if needle in prompt:
                chosen = doc_type
                break
        return type("Resp", (), {"choices": [StubChoice(chosen)]})


class StubOpenAIClient:
    def __init__(self, mapping):
        self.chat = StubChat(mapping)
        self.api_key = "stub"


def make_pdf(path: Path, text: str):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    doc.save(path)
    doc.close()


def test_classify_doc_type_llm_stub(monkeypatch, mcp_servers):
    from python import server

    # Stub OpenAI client with deterministic mapping
    mapping = {
        "Sales Agreement": "sales_agreement",
        "DISTRIBUTOR AGREEMENT": "distributor_agreement",
        "MUTUAL NON-DISCLOSURE AGREEMENT": "nda",
        "LETTER OF INTENT": "letter_of_intent",
    }
    stub_client = StubOpenAIClient(mapping)
    monkeypatch.setattr(server, "openai_client", stub_client)

    # Use the MCP servers from the fixture
    monkeypatch.setenv("MCP_OCR_URL", mcp_servers["ocr_url"])
    monkeypatch.setenv("MCP_RAG_URL", mcp_servers["rag_url"])

    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        files = {
            "test_sales.pdf": "Sales Agreement\nThis agreement is between A and B.",
            "test_distributor.pdf": "DISTRIBUTOR AGREEMENT\nBetween X and Y.",
            "test_nda.pdf": "MUTUAL NON-DISCLOSURE AGREEMENT\nBetween P and Q.",
            "test_loi.pdf": "LETTER OF INTENT\nBetween Foo and Bar.",
        }
        expected = {
            "test_sales.pdf": "sales_agreement",
            "test_distributor.pdf": "distributor_agreement",
            "test_nda.pdf": "nda",
            "test_loi.pdf": "letter_of_intent",
        }

        paths = []
        for fname, text in files.items():
            p = tmp / fname
            make_pdf(p, text)
            paths.append(p)

        results = {}
        for p in paths:
            dt = server.classify_doc_type(p.name, str(p))
            results[p.name] = dt

        assert results == expected

