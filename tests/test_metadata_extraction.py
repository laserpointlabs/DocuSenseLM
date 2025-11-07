import os
import json as json_module
from typing import Any

import pytest

from ingest.clause_extractor import clause_extractor
from ingest.llm_refiner import refine_metadata


@pytest.fixture
def sample_clause_text() -> str:
    return (
        "THIS MUTUAL NON-DISCLOSURE AGREEMENT (the \"Agreement\") is made and entered into as of "
        "June 16, 2025 (the \"Effective Date\") by and between Fanuc America Corporation, a Michigan "
        "corporation with offices at 3900 W Hamlin Road, Rochester Hills, MI 48309 (\"Discloser\") and "
        "Kidde-Fenwal, LLC, a Delaware limited liability company with offices at 400 Main Street, "
        "Ashland, MA 01721 (\"Recipient\").\n\n"
        "NOW, THEREFORE, in consideration of the mutual promises herein, the parties agree as follows:\n"
        "This Agreement shall remain in effect for three (3) years (36 months) from the Effective Date.\n"
        "This Agreement will be governed by the laws of the State of California excluding conflicts of law principles."
    )


@pytest.fixture
def sample_pages(sample_clause_text: str) -> list[dict[str, Any]]:
    return [
        {
            "page_num": 1,
            "text": sample_clause_text,
            "span_start": 0,
            "span_end": len(sample_clause_text),
        }
    ]


def test_clause_extractor_metadata(sample_clause_text: str, sample_pages: list[dict[str, Any]]):
    result = clause_extractor.extract(sample_clause_text, sample_pages)
    metadata = result["metadata"]

    party_names = {p["name"] for p in metadata["parties"]}
    assert any("Fanuc America Corporation" in name for name in party_names)
    assert any("Kidde-Fenwal" in name for name in party_names)
    assert metadata["governing_law"] == "State of California"
    assert metadata["term_months"] == 36
    assert metadata["is_mutual"] is True
    assert metadata["confidence_score"] < 1.0
    assert "party_addresses" in metadata["missing_fields"]


class _StubResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _StubClient:
    def __init__(self, *_, **__):
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, *, json: dict[str, Any]):
        self.requests.append((url, json))
        refinement_json = json_module.dumps(
            {
                "parties": [
                    {
                        "name": "Fanuc America Corporation",
                        "address": "3900 W Hamlin Road, Rochester Hills, MI 48309",
                        "type": "disclosing",
                    },
                    {
                        "name": "Kidde-Fenwal, LLC",
                        "address": "400 Main Street, Ashland, MA 01721",
                        "type": "receiving",
                    },
                ],
                "governing_law": "State of California",
                "effective_date": "2025-06-16",
                "term_months": 36,
                "is_mutual": True,
            }
        )
        response_payload = {"response": refinement_json}
        return _StubResponse(response_payload)


@pytest.fixture
def enable_llm_refinement(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_REFINEMENT", "true")
    monkeypatch.setenv("LLM_ENDPOINT", "http://localhost:11434")
    monkeypatch.setenv("LLM_EXTRACTION_MODEL", "test-model")
    monkeypatch.setenv("LLM_REFINER_CONFIDENCE_THRESHOLD", "0.9")
    monkeypatch.setenv("LLM_REFINER_TIMEOUT", "10")
    monkeypatch.setattr("ingest.llm_refiner.httpx.Client", _StubClient)
    yield
    monkeypatch.delenv("ENABLE_LLM_REFINEMENT", raising=False)
    monkeypatch.delenv("LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("LLM_EXTRACTION_MODEL", raising=False)
    monkeypatch.delenv("LLM_REFINER_CONFIDENCE_THRESHOLD", raising=False)
    monkeypatch.delenv("LLM_REFINER_TIMEOUT", raising=False)


def test_llm_refiner_enriches_metadata(enable_llm_refinement, sample_clause_text):
    initial_metadata = {
        "parties": [
            {"name": "Fanuc America Corporation", "type": None, "address": None},
            {"name": "Kidde-Fenwal, LLC", "type": None, "address": None},
        ],
        "governing_law": None,
        "term_months": None,
        "is_mutual": None,
        "confidence_score": 0.2,
        "missing_fields": ["party_addresses", "governing_law", "term_months", "mutuality"],
    }

    refined, info = refine_metadata(initial_metadata, sample_clause_text)

    assert info["applied"] is True
    assert refined["parties"][0]["address"] == "3900 W Hamlin Road, Rochester Hills, MI 48309"
    assert refined["parties"][1]["address"] == "400 Main Street, Ashland, MA 01721"
    assert refined["governing_law"] == "State of California"
    assert refined["term_months"] == 36
    assert refined["is_mutual"] is True
    assert refined["extraction_method"] == "heuristic+llm"
    assert refined["confidence_score"] >= info["confidence_before"]
    assert "raw_response" in info
