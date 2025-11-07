from pathlib import Path
import uuid

from ingest.worker import worker
from api.db import get_db_session
from api.db.schema import Document as DocumentModel, DocumentStatus
from api.services.registry_service import registry_service


def test_ingestion_pipeline_with_in_memory_services(tmp_path, fake_service_registry, monkeypatch):
    dummy_path = Path(tmp_path) / "dummy.txt"
    dummy_path.write_text("placeholder")

    def fake_parse(_file_path: str):
        text = "Mutual NDA between Acme Inc. and Beta Corp. Confidential Information includes trade secrets."
        return {
            "text": text,
            "pages": [
                {
                    "page_num": 1,
                    "text": text,
                    "is_scanned": False,
                    "span_start": 0,
                    "span_end": len(text),
                }
            ],
            "metadata": {},
        }

    def fake_extract(_full_text, _pages):
        return {
            "title": "Mutual Non-Disclosure Agreement",
            "recitals": [],
            "clauses": [
                {
                    "text": "The parties agree to keep all trade secrets confidential.",
                    "clause_number": "1",
                    "page_num": 1,
                    "span_start": 0,
                    "span_end": 63,
                }
            ],
            "metadata": {
                "parties": [
                    {"name": "Acme Inc.", "type": "disclosing"},
                    {"name": "Beta Corp.", "type": "receiving"},
                ]
            },
        }

    monkeypatch.setattr("ingest.parser.parser.parse", fake_parse)
    monkeypatch.setattr("ingest.clause_extractor.clause_extractor.extract", fake_extract)
    monkeypatch.setattr("ingest.ocr_detector.ocr_detector.needs_ocr", lambda pages: False)

    document_id = worker.ingest_document(str(dummy_path), dummy_path.name)
    document_uuid = uuid.UUID(document_id)

    db = get_db_session()
    try:
        stored = db.query(DocumentModel).filter(DocumentModel.id == document_uuid).first()
        assert stored is not None
        assert stored.status == DocumentStatus.PROCESSED
    finally:
        db.close()

    bm25_backend = fake_service_registry["bm25"]
    vector_backend = fake_service_registry["vector"]
    assert any(doc.doc_id == document_id for doc in bm25_backend.documents.values())
    assert any(doc.doc_id == document_id for doc in vector_backend.documents.values())

    records = registry_service.search_records()
    assert records
    assert any(str(record.document_id) == document_id for record in records if record.document_id)
