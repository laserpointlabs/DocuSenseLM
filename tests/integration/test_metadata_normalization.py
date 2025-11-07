from datetime import datetime
from pathlib import Path
import uuid

from ingest.worker import worker
from api.db import get_db_session
from api.db.schema import Document, DocumentMetadata, Party


def create_dummy_file(tmp_path: Path, content: str = "placeholder") -> Path:
    path = tmp_path / "dummy.txt"
    path.write_text(content)
    return path


def test_metadata_normalization_persists_document_metadata(tmp_path, fake_service_registry, monkeypatch):
    dummy_path = create_dummy_file(tmp_path)

    parser_metadata = {"num_pages": 1, "title": "NDA"}

    def fake_parse(_file_path: str):
        text = "Agreement between Example Corp and Sample LLC."
        return {
            "text": text,
            "pages": [
                {"page_num": 1, "text": text, "is_scanned": False, "span_start": 0, "span_end": len(text)}
            ],
            "metadata": parser_metadata,
        }

    extracted_metadata = {
        "parties": [
            {"name": "Example Corp", "type": "disclosing", "address": "1 Main"},
            {"name": "Sample LLC", "type": "receiving", "address": "2 Side"},
        ],
        "effective_date": datetime(2024, 1, 15),
        "governing_law": "Delaware",
        "is_mutual": True,
        "term_months": 24,
        "survival_months": 12,
    }

    def fake_extract(_full_text, _pages):
        return {
            "title": "Mutual NDA",
            "recitals": [],
            "clauses": [],
            "metadata": extracted_metadata,
        }

    monkeypatch.setattr("ingest.parser.parser.parse", fake_parse)
    monkeypatch.setattr("ingest.clause_extractor.clause_extractor.extract", fake_extract)
    monkeypatch.setattr("ingest.ocr_detector.ocr_detector.needs_ocr", lambda pages: False)

    document_id = worker.ingest_document(str(dummy_path), dummy_path.name)
    document_uuid = uuid.UUID(document_id)

    db = get_db_session()
    try:
        doc = db.query(Document).filter(Document.id == document_uuid).first()
        assert doc is not None
        assert doc.metadata_json == parser_metadata

        metadata_row = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_uuid).first()
        assert metadata_row is not None
        assert metadata_row.effective_date is not None
        assert metadata_row.effective_date.replace(tzinfo=None) == extracted_metadata["effective_date"]
        assert metadata_row.governing_law == "Delaware"
        assert metadata_row.is_mutual is True
        assert metadata_row.term_months == 24
        assert metadata_row.survival_months == 12

        parties = db.query(Party).filter(Party.document_id == document_uuid).all()
        assert len(parties) == 2
        names = {party.party_name for party in parties}
        assert {"Example Corp", "Sample LLC"} == names
    finally:
        db.close()
