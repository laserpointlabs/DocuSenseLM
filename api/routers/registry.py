"""
Registry router: deterministic NDA registry endpoints.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.models.responses import (
    ActiveNDAResponse,
    ActiveNDAMatch,
    NDAEventResponse,
    NDARegistryResponse,
    NDARecordSummary,
)
from api.services.registry_service import registry_service


router = APIRouter(prefix="/registry", tags=["registry"])


def _to_summary(record) -> NDARecordSummary:
    """Convert ORM record to Pydantic summary."""
    return NDARecordSummary(
        id=str(record.id),
        document_id=str(record.document_id) if record.document_id else None,
        counterparty_name=record.counterparty_name,
        counterparty_domain=record.counterparty_domain,
        status=record.status,
        direction=record.direction,
        nda_type=record.nda_type,
        entity_id=record.entity_id,
        owner_user_id=str(record.owner_user_id) if record.owner_user_id else None,
        effective_date=record.effective_date,
        expiry_date=record.expiry_date,
        term_months=record.term_months,
        survival_months=record.survival_months,
        tags=record.tags or {},
        file_uri=record.file_uri,
        workflow_instance_id=str(record.workflow_instance_id) if record.workflow_instance_id else None,
    )


@router.get("/search", response_model=NDARegistryResponse)
def search_registry(
    query: Optional[str] = Query(None, description="Full-text search query"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
) -> NDARegistryResponse:
    """Search NDA registry."""
    records = registry_service.search_records(query=query, status=status, limit=limit)
    return NDARegistryResponse(
        results=[_to_summary(record) for record in records],
        total=len(records),
    )


@router.get("/check", response_model=ActiveNDAResponse)
def check_active_nda(
    domain: Optional[str] = Query(None, description="Counterparty domain"),
    name: Optional[str] = Query(None, description="Counterparty name (fallback)"),
    on_date: Optional[date] = Query(None, alias="on", description="Date to evaluate"),
) -> ActiveNDAResponse:
    """Check if an NDA is active for a counterparty."""
    target = domain or name
    if not target:
        raise HTTPException(status_code=400, detail="Provide either domain or name")

    matches = registry_service.active_for_party(
        domain_or_name=target,
        on_date=on_date,
    )

    return ActiveNDAResponse(
        query=target,
        as_of=on_date or date.today(),
        active=bool(matches),
        matches=[
            ActiveNDAMatch(
                id=str(record.id),
                counterparty_name=record.counterparty_name,
                counterparty_domain=record.counterparty_domain,
                effective_date=record.effective_date,
                expiry_date=record.expiry_date,
                status=record.status,
                file_uri=record.file_uri,
            )
            for record in matches
        ],
    )


@router.get("/expiring", response_model=NDARegistryResponse)
def expiring_registry(
    window_days: int = Query(30, ge=1, le=365, description="Look-ahead window in days"),
    status: str = Query("signed", description="Status to filter"),
    as_of: Optional[date] = Query(None, description="Reference date"),
) -> NDARegistryResponse:
    """List NDAs expiring within a window."""
    records = registry_service.expiring_within(
        window_days=window_days,
        status=status,
        as_of=as_of,
    )
    return NDARegistryResponse(
        results=[_to_summary(record) for record in records],
        total=len(records),
    )


@router.get("/events/pending", response_model=List[NDAEventResponse])
def pending_events() -> List[NDAEventResponse]:
    """Return NDA lifecycle events not yet delivered."""
    events = registry_service.pending_events()
    return [
        NDAEventResponse(
            id=event.id,
            nda_id=str(event.nda_id),
            kind=event.kind,
            scheduled_for=event.scheduled_for,
            delivered_at=event.delivered_at,
            payload=event.payload or {},
        )
        for event in events
    ]
