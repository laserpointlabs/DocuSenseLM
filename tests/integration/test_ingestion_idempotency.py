import uuid
from pathlib import Path

import pytest

from ingest.worker import worker
from api.db import get_db_session
from api.db.schema import Document, DocumentStatus


def create_dummy_file(tmp_path: Path, content: str = "placeholder") -> Path:
    path = tmp_path / "dummy.txt"
    path.write_text(content)
    return path


def test_ingest_same_file_twice_returns_same_document(tmp_path, fake_service_registry, monkeypatch):
    dummy_path = create_dummy_file(tmp_path)

    def fake_parse(_file_path: str):
        text = "Mutual NDA between Gamma Corp and Delta Inc."
        return {
            "text": text,
            "pages": [
                {"page_num": 1, "text": text, "is_scanned": False, "span_start": 0, "span_end": len(text)}
            ],
            "metadata": {},
        }

    def fake_extract(_full_text, _pages):
        return {
            "title": "Mutual NDA",
            "recitals": [],
            "clauses": [
                {
                    "text": "1. Confidential information must remain protected.",
                    "clause_number": "1",
                    "title": "Confidentiality",
                    "page_num": 1,
                    "span_start": 0,
                    "span_end": 60,
                }
            ],
            "metadata": {
                "parties": [
                    {"name": "Gamma Corp", "type": "disclosing"},
                    {"name": "Delta Inc.", "type": "receiving"},
                ]
            },
        }

    monkeypatch.setattr("ingest.parser.parser.parse", fake_parse)
    monkeypatch.setattr("ingest.clause_extractor.clause_extractor.extract", fake_extract)
    monkeypatch.setattr("ingest.ocr_detector.ocr_detector.needs_ocr", lambda pages: False)

    first_id = worker.ingest_document(str(dummy_path), dummy_path.name)
    second_id = worker.ingest_document(str(dummy_path), dummy_path.name)

    assert first_id == second_id

    db = get_db_session()
    try:
        stored = db.query(Document).filter(Document.id == uuid.UUID(first_id)).first()
        assert stored is not None
        assert stored.status == DocumentStatus.PROCESSED
    finally:
        db.close()


def test_ingest_duplicate_file_without_id_raises(tmp_path, fake_service_registry, monkeypatch):
    dummy_path = create_dummy_file(tmp_path)

    monkeypatch.setattr("ingest.parser.parser.parse", lambda _: {"text": "", "pages": [], "metadata": {}})
    monkeypatch.setattr(
        "ingest.clause_extractor.clause_extractor.extract",
        lambda *_: {"title": None, "recitals": [], "clauses": [], "metadata": {"parties": []}},
    )
    monkeypatch.setattr("ingest.ocr_detector.ocr_detector.needs_ocr", lambda pages: False)

    worker.ingest_document(str(dummy_path), dummy_path.name)

    with pytest.raises(ValueError):
        worker.ingest_document(str(dummy_path), dummy_path.name, document_id=str(uuid.uuid4()))
