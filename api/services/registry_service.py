"""
Registry service for deterministic NDA lookups and lifecycle events.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from api.db import get_db_session
from api.db.schema import NDAEvent, NDARecord
from dateutil.relativedelta import relativedelta


def _serialize_for_json(value: Any) -> Any:
    """Recursively serialize objects (e.g., datetime) to JSON-safe values."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_for_json(v) for v in value]
    return value


class RegistryService:
    """Service layer for NDA registry operations."""

    EXPIRY_WINDOWS = (90, 60, 30)

    def upsert_record(
        self,
        *,
        document_id: Optional[Any],
        counterparty_name: str,
        counterparty_domain: Optional[str],
        entity_id: Optional[str],
        owner_user_id: Optional[Any],
        direction: Optional[str],
        nda_type: Optional[str],
        effective_date: Optional[date],
        term_months: Optional[int],
        survival_months: Optional[int],
        status: str,
        file_uri: str,
        file_bytes: bytes,
        extracted_text: Optional[str],
        template_id: Optional[str] = None,
        template_version: Optional[int] = None,
        tags: Optional[Dict[str, Any]] = None,
        facts: Optional[Dict[str, Any]] = None,
    ) -> NDARecord:
        """
        Create or update an NDA registry record. Schedules lifecycle events automatically.
        """
        sha_bytes = hashlib.sha256(file_bytes).digest()
        today = date.today()

        doc_uuid: Optional[UUID] = None
        if document_id is not None:
            doc_uuid = document_id if isinstance(document_id, UUID) else UUID(str(document_id))

        owner_uuid: Optional[UUID] = None
        if owner_user_id is not None:
            owner_uuid = owner_user_id if isinstance(owner_user_id, UUID) else UUID(str(owner_user_id))

        if effective_date and term_months:
            expiry_candidate = effective_date + relativedelta(months=term_months)
        else:
            expiry_candidate = None

        # Determine canonical status (auto-expire if past)
        canonical_status = status
        if expiry_candidate and expiry_candidate < today and status == "signed":
            canonical_status = "expired"

        session = get_db_session()
        try:
            record = (
                session.query(NDARecord)
                .filter(
                    or_(
                        NDARecord.document_id == doc_uuid if doc_uuid else False,
                        NDARecord.file_sha256 == sha_bytes,
                    )
                )
                .order_by(NDARecord.updated_at.desc())
                .first()
            )

            is_new_record = record is None
            if is_new_record:
                record = NDARecord(
                    document_id=doc_uuid,
                    file_sha256=sha_bytes,
                )

            record.counterparty_name = counterparty_name
            record.counterparty_domain = counterparty_domain
            record.entity_id = entity_id
            record.owner_user_id = owner_uuid
            record.direction = direction
            record.nda_type = nda_type
            record.effective_date = effective_date
            record.term_months = term_months
            record.survival_months = survival_months
            record.expiry_date = expiry_candidate
            record.status = canonical_status
            record.file_uri = file_uri
            record.extracted_text = extracted_text
            record.tags = tags or {}
            record.facts_json = _serialize_for_json(facts) if facts else None
            
            # Set template tracking if provided
            if template_id:
                try:
                    template_uuid = UUID(str(template_id))
                    record.template_id = template_uuid
                    record.template_version = template_version
                except ValueError:
                    logger.warning(f"Invalid template_id: {template_id}")

            session.add(record)
            session.flush()

            self._schedule_events(session, record)

            session.commit()
            session.refresh(record)
            return record
        except IntegrityError as exc:  # pragma: no cover - unexpected duplicates
            session.rollback()
            raise exc
        finally:
            session.close()

    def search_records(
        self,
        *,
        query: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[NDARecord]:
        """Full-text search for NDAs."""
        session = get_db_session()
        try:
            q = session.query(NDARecord)

            if status:
                q = q.filter(NDARecord.status == status)

            if query:
                dialect = session.bind.dialect.name
                like_clause = f"%{query}%"
                if dialect == "postgresql":
                    q = q.filter(
                        NDARecord.text_tsv.op("@@")(func.plainto_tsquery("english", query))
                        | NDARecord.counterparty_name.ilike(like_clause)
                        | NDARecord.counterparty_domain.ilike(like_clause)
                    )
                else:
                    q = q.filter(
                        or_(
                            NDARecord.counterparty_name.ilike(like_clause),
                            NDARecord.counterparty_domain.ilike(like_clause),
                            NDARecord.extracted_text.ilike(like_clause),
                        )
                    )

            return (
                q.order_by(NDARecord.expiry_date.asc().nulls_last())
                .limit(limit)
                .all()
            )
        finally:
            session.close()

    def active_for_party(
        self,
        *,
        domain_or_name: str,
        on_date: Optional[date] = None,
    ) -> List[NDARecord]:
        """Return active NDAs for a party (domain or fuzzy name)."""
        on_date = on_date or date.today()
        like_clause = f"%{domain_or_name}%"

        session = get_db_session()
        try:
            results = (
                session.query(NDARecord)
                .filter(
                    NDARecord.status == "signed",
                    NDARecord.effective_date <= on_date,
                    or_(NDARecord.expiry_date.is_(None), NDARecord.expiry_date >= on_date),
                    or_(
                        NDARecord.counterparty_domain == domain_or_name,
                        NDARecord.counterparty_name.ilike(like_clause),
                    ),
                )
                .order_by(NDARecord.expiry_date.asc().nulls_last())
                .all()
            )
            return results
        finally:
            session.close()

    def expiring_within(
        self,
        *,
        window_days: int,
        status: str = "signed",
        as_of: Optional[date] = None,
    ) -> List[NDARecord]:
        """Return NDAs expiring within the given window."""
        as_of = as_of or date.today()
        upper = as_of + timedelta(days=window_days)

        session = get_db_session()
        try:
            return (
                session.query(NDARecord)
                .filter(
                    NDARecord.status == status,
                    NDARecord.expiry_date.isnot(None),
                    NDARecord.expiry_date >= as_of,
                    NDARecord.expiry_date <= upper,
                )
                .order_by(NDARecord.expiry_date.asc())
                .all()
            )
        finally:
            session.close()

    def pending_events(self) -> List[NDAEvent]:
        """Return events that have not been delivered yet."""
        session = get_db_session()
        try:
            return (
                session.query(NDAEvent)
                .filter(NDAEvent.delivered_at.is_(None))
                .order_by(NDAEvent.scheduled_for.asc())
                .all()
            )
        finally:
            session.close()

    def mark_event_delivered(self, event_id: int) -> None:
        """Mark an event as delivered."""
        session = get_db_session()
        try:
            event = session.query(NDAEvent).filter(NDAEvent.id == event_id).first()
            if event:
                event.delivered_at = datetime.now(timezone.utc)
                session.commit()
        finally:
            session.close()

    def _schedule_events(self, session, record: NDARecord) -> None:
        """Ensure lifecycle events exist for an NDA."""
        if not record.expiry_date or record.status != "signed":
            session.query(NDAEvent).filter(
                NDAEvent.nda_id == record.id,
                NDAEvent.delivered_at.is_(None),
            ).delete(synchronize_session=False)
            return

        expiry_datetime = datetime.combine(record.expiry_date, time.min).replace(tzinfo=timezone.utc)

        events_to_create: List[Tuple[str, datetime]] = []
        for window in self.EXPIRY_WINDOWS:
            scheduled_for = expiry_datetime - timedelta(days=window)
            if scheduled_for >= datetime.now(timezone.utc):
                events_to_create.append((f"nda.expiring_{window}d", scheduled_for))

        events_to_create.append(("nda.expired", expiry_datetime))

        existing_events: Sequence[NDAEvent] = (
            session.query(NDAEvent)
            .filter(
                NDAEvent.nda_id == record.id,
                NDAEvent.kind.in_(event_kind for event_kind, _ in events_to_create),
            )
            .all()
        )
        existing_key = {
            (
                evt.kind,
                (evt.scheduled_for.astimezone(timezone.utc) if evt.scheduled_for.tzinfo else evt.scheduled_for.replace(tzinfo=timezone.utc)).replace(microsecond=0),
            )
            for evt in existing_events
        }

        for kind, scheduled_for in events_to_create:
            key = (kind, scheduled_for.replace(microsecond=0))
            if key in existing_key:
                continue

            payload = {
                "nda_id": str(record.id),
                "counterparty": record.counterparty_name,
                "expiry_date": record.expiry_date.isoformat() if record.expiry_date else None,
                "owner_user_id": str(record.owner_user_id) if record.owner_user_id else None,
                "file_uri": record.file_uri,
            }

            session.add(
                NDAEvent(
                    nda_id=record.id,
                    kind=kind,
                    scheduled_for=scheduled_for,
                    payload=_serialize_for_json(payload),
                )
            )


# Global singleton
registry_service = RegistryService()
