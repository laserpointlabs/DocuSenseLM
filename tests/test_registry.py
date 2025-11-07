from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import registry as registry_router
from api.services.registry_service import registry_service


def _create_sample_record(status: str = "signed", term_months: int = 8):
    today = date.today()
    return registry_service.upsert_record(
        document_id=str(uuid4()),
        counterparty_name="Acme Corp",
        counterparty_domain="acme.com",
        entity_id="Entity-1",
        owner_user_id=None,
        direction="outbound",
        nda_type="mutual",
        effective_date=today,
        term_months=term_months,
        survival_months=12,
        status=status,
        file_uri="nda-raw/acme.pdf",
        file_bytes=b"sample pdf contents",
        extracted_text="This NDA covers confidential information.",
        tags={"governing_law": "Delaware"},
        facts={"metadata": {"governing_law": "Delaware"}},
    )


def test_registry_service_end_to_end():
    record = _create_sample_record()

    assert record.counterparty_name == "Acme Corp"
    assert record.expiry_date is not None

    search_results = registry_service.search_records(query="Acme")
    assert len(search_results) == 1

    active = registry_service.active_for_party(domain_or_name="acme.com")
    assert len(active) == 1

    expiring = registry_service.expiring_within(window_days=300)
    assert len(expiring) == 1

    events = registry_service.pending_events()
    kinds = {event.kind for event in events}
    assert kinds == {"nda.expiring_90d", "nda.expiring_60d", "nda.expiring_30d", "nda.expired"}


def test_registry_updates_existing_record_by_file_sha():
    record = _create_sample_record()

    original_id = record.id
    original_document_id = record.document_id

    updated = registry_service.upsert_record(
        document_id=str(uuid4()),
        counterparty_name="Acme Corp",
        counterparty_domain="acme.com",
        entity_id="Entity-2",
        owner_user_id=None,
        direction="inbound",
        nda_type="one_way",
        effective_date=record.effective_date,
        term_months=record.term_months,
        survival_months=record.survival_months,
        status="signed",
        file_uri="nda-raw/acme.pdf",
        file_bytes=b"sample pdf contents",
        extracted_text="Updated terms",
        tags={"governing_law": "California"},
        facts={"metadata": {"governing_law": "California"}},
    )

    assert updated.id == original_id
    assert updated.document_id == original_document_id
    assert updated.entity_id == "Entity-2"
    assert updated.direction == "inbound"


def test_registry_auto_expires_signed_if_past_term():
    past_date = date.today() - timedelta(days=730)
    record = registry_service.upsert_record(
        document_id=str(uuid4()),
        counterparty_name="Old NDA",
        counterparty_domain="legacy.example",
        entity_id="Entity-Old",
        owner_user_id=None,
        direction="outbound",
        nda_type="mutual",
        effective_date=past_date,
        term_months=6,
        survival_months=12,
        status="signed",
        file_uri="nda-raw/legacy.pdf",
        file_bytes=b"legacy",
        extracted_text="",
        tags={},
        facts=None,
    )

    assert record.status == "expired"


def test_registry_event_deduplication():
    record = _create_sample_record()
    first_events = registry_service.pending_events()
    assert len(first_events) == 4

    registry_service.upsert_record(
        document_id=str(record.document_id) if record.document_id else None,
        counterparty_name="Acme Corp",
        counterparty_domain="acme.com",
        entity_id="Entity-1",
        owner_user_id=None,
        direction="outbound",
        nda_type="mutual",
        effective_date=record.effective_date,
        term_months=record.term_months,
        survival_months=record.survival_months,
        status="signed",
        file_uri="nda-raw/acme.pdf",
        file_bytes=b"sample pdf contents",
        extracted_text="Updated NDA text",
        tags={"governing_law": "Delaware"},
        facts={"metadata": {"governing_law": "Delaware"}},
    )

    second_events = registry_service.pending_events()
    assert len(second_events) == 4


def test_registry_mark_event_delivered():
    _create_sample_record()
    events = registry_service.pending_events()
    target = events[0]

    registry_service.mark_event_delivered(target.id)

    remaining_ids = {event.id for event in registry_service.pending_events()}
    assert target.id not in remaining_ids


def test_registry_update_clears_events_for_non_signed_status():
    record = _create_sample_record()
    assert registry_service.pending_events()

    registry_service.upsert_record(
        document_id=str(record.document_id) if record.document_id else None,
        counterparty_name="Acme Corp",
        counterparty_domain="acme.com",
        entity_id="Entity-1",
        owner_user_id=None,
        direction="outbound",
        nda_type="mutual",
        effective_date=record.effective_date,
        term_months=record.term_months,
        survival_months=record.survival_months,
        status="terminated",
        file_uri="nda-raw/acme.pdf",
        file_bytes=b"sample pdf contents",
        extracted_text="Updated NDA text",
        tags={"governing_law": "Delaware"},
        facts={"metadata": {"governing_law": "Delaware"}},
    )

    updated = registry_service.search_records(query="Acme")[0]
    assert updated.status == "terminated"
    assert registry_service.pending_events() == []


@pytest.fixture
def client():
    test_app = FastAPI()
    test_app.include_router(registry_router.router)
    return TestClient(test_app)


def test_registry_routes(client):
    _create_sample_record()

    resp = client.get("/registry/check", params={"domain": "acme.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["active"] is True
    assert data["matches"][0]["counterparty_name"] == "Acme Corp"

    resp = client.get("/registry/search", params={"query": "Acme"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = client.get("/registry/expiring", params={"window_days": 300})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = client.get("/registry/events/pending")
    assert resp.status_code == 200
    assert len(resp.json()) == 4
