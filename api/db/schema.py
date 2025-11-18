"""
PostgreSQL database schema for NDA Dashboard
"""
from sqlalchemy import (
    Column, Integer, String, DateTime, Date, Boolean, Text, JSON,
    Float, ForeignKey, Index, Enum, LargeBinary, CheckConstraint,
    UniqueConstraint, DDL, event, text
)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum

Base = declarative_base()


class TSVectorType(TypeDecorator):
    """Dialect-aware TSVECTOR column that falls back to TEXT."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):  # pragma: no cover - depends on dialect
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR

            return dialect.type_descriptor(PG_TSVECTOR())
        return dialect.type_descriptor(Text())


class DocumentStatus(enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED)
    s3_path = Column(String(512), nullable=True)  # Path in MinIO/S3
    metadata_json = Column(JSON, nullable=True)
    file_sha256 = Column(LargeBinary, nullable=True, unique=True)

    # Indexes
    __table_args__ = (
        Index('idx_documents_status', 'status'),
        Index('idx_documents_upload_date', 'upload_date'),
        UniqueConstraint('file_sha256', name='uq_documents_file_sha'),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    section_type = Column(String(50), nullable=True)  # e.g., "clause", "recital", "signature"
    clause_number = Column(String(20), nullable=True)  # e.g., "1", "2.1", "WHEREAS"
    clause_title = Column(String(200), nullable=True)  # Extracted clause title (e.g., "Definition", "Protection of Confidential Information")
    text = Column(Text, nullable=False)
    page_num = Column(Integer, nullable=False)
    span_start = Column(Integer, nullable=False)  # Character offset start
    span_end = Column(Integer, nullable=False)    # Character offset end

    # Indexes
    __table_args__ = (
        Index('idx_chunks_document_id', 'document_id'),
        Index('idx_chunks_section_type', 'section_type'),
        Index('idx_chunks_clause_number', 'clause_number'),
    )


class Party(Base):
    __tablename__ = "parties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    party_name = Column(String(255), nullable=False)
    party_type = Column(String(50), nullable=False)  # "disclosing" or "receiving"
    address = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_parties_document_id', 'document_id'),
        Index('idx_parties_party_name', 'party_name'),
        Index('idx_parties_party_type', 'party_type'),
    )


class DocumentMetadata(Base):
    __tablename__ = "document_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, unique=True)
    effective_date = Column(DateTime(timezone=True), nullable=True)
    governing_law = Column(String(100), nullable=True)  # e.g., "Delaware", "New York"
    is_mutual = Column(Boolean, nullable=True)  # True if mutual NDA, False if unilateral
    term_months = Column(Integer, nullable=True)  # Duration of NDA in months
    survival_months = Column(Integer, nullable=True)  # Survival period after expiration

    # Indexes
    __table_args__ = (
        Index('idx_metadata_document_id', 'document_id'),
        Index('idx_metadata_effective_date', 'effective_date'),
        Index('idx_metadata_governing_law', 'governing_law'),
        Index('idx_metadata_is_mutual', 'is_mutual'),
    )


# Competency Question System Tables

class QuestionCategory(Base):
    __tablename__ = "question_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    parent_category_id = Column(UUID(as_uuid=True), ForeignKey("question_categories.id"), nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_categories_parent', 'parent_category_id'),
    )


class CompetencyQuestion(Base):
    __tablename__ = "competency_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_text = Column(Text, nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("question_categories.id"), nullable=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)  # Associate with specific document
    verification_hint = Column(Text, nullable=True)  # Instructions for verifying the answer
    expected_clause = Column(String(200), nullable=True)  # Expected clause title/number
    expected_page = Column(Integer, nullable=True)  # Expected page number for verification
    expected_answer_text = Column(Text, nullable=True)  # Expected answer for validation
    confidence_threshold = Column(Float, default=0.7)  # Confidence threshold for passing tests
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

    # Indexes
    __table_args__ = (
        Index('idx_questions_category', 'category_id'),
        Index('idx_questions_active', 'is_active'),
        Index('idx_questions_created_at', 'created_at'),
        Index('idx_questions_document', 'document_id'),
    )


class QuestionGroundTruth(Base):
    __tablename__ = "question_ground_truth"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("competency_questions.id"), nullable=False)
    expected_clause_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=True)
    expected_answer_text = Column(Text, nullable=True)
    validation_method = Column(String(50), nullable=False)  # "exact_match", "clause_match", "semantic"
    confidence_score = Column(Float, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_ground_truth_question', 'question_id'),
        Index('idx_ground_truth_clause', 'expected_clause_id'),
    )


class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("competency_questions.id"), nullable=False)
    run_at = Column(DateTime(timezone=True), server_default=func.now())
    answer_text = Column(Text, nullable=True)
    retrieved_clauses = Column(JSON, nullable=True)  # Array of clause IDs (deprecated, use citations_json)
    citations_json = Column(JSON, nullable=True)  # Full citation data: [{doc_id, clause_number, page_num, span_start, span_end, source_uri, excerpt}]
    accuracy_score = Column(Float, nullable=True)
    response_time_ms = Column(Integer, nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_test_runs_question', 'question_id'),
        Index('idx_test_runs_run_at', 'run_at'),
    )


class TestFeedback(Base):
    __tablename__ = "test_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_run_id = Column(UUID(as_uuid=True), ForeignKey("test_runs.id"), nullable=False)
    user_feedback = Column(String(20), nullable=False)  # "correct" or "incorrect"
    feedback_text = Column(Text, nullable=True)
    feedback_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index('idx_feedback_test_run', 'test_run_id'),
    )


class NDARecord(Base):
    """
    Canonical NDA registry entry.
    Stores normalized metadata used for deterministic lookups and lifecycle events.
    """
    __tablename__ = "nda_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True, unique=True)
    direction = Column(String(20), nullable=True)
    nda_type = Column(String(20), nullable=True)
    counterparty_name = Column(String(255), nullable=False)
    counterparty_domain = Column(String(255), nullable=True)
    entity_id = Column(String(255), nullable=True)
    owner_user_id = Column(UUID(as_uuid=True), nullable=True)
    effective_date = Column(Date, nullable=True)
    term_months = Column(Integer, nullable=True)
    survival_months = Column(Integer, nullable=True)
    expiry_date = Column(Date, nullable=True)
    status = Column(String(50), nullable=False, default="signed")
    file_uri = Column(String(512), nullable=False)
    file_sha256 = Column(LargeBinary, nullable=False, unique=True)
    extracted_text = Column(Text, nullable=True)
    text_tsv = Column(TSVectorType())
    tags = Column(JSON, nullable=False, default=dict)
    facts_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    workflow_instance_id = Column(UUID(as_uuid=True), ForeignKey("nda_workflow_instances.id"), nullable=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("nda_templates.id"), nullable=True)  # Template used to create this NDA
    template_version = Column(Integer, nullable=True)  # Version of template used

    __table_args__ = (
        UniqueConstraint('document_id', name='uq_nda_records_document_id'),
        CheckConstraint(
            "status IN ('created','draft','negotiating','customer_signed','llm_reviewed_approved','llm_reviewed_rejected','reviewed','approved','rejected','signed','archived','expired','active','terminated')",
            name='chk_nda_records_status'
        ),
        Index('idx_nda_records_counterparty', 'counterparty_domain', 'counterparty_name'),
        Index('idx_nda_records_expiry_signed', 'expiry_date',
              postgresql_where=text("status = 'signed'")),
        Index('idx_nda_records_text_tsv', 'text_tsv', postgresql_using='gin'),
        Index('idx_nda_records_status', 'status'),
        Index('idx_nda_records_workflow_instance', 'workflow_instance_id'),
    )


class NDAEvent(Base):
    """
    Lifecycle events for NDAs (expiring windows, conflicts, etc.).
    """
    __tablename__ = "nda_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nda_id = Column(UUID(as_uuid=True), ForeignKey("nda_records.id"), nullable=False)
    kind = Column(String(50), nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_nda_events_pending', 'kind', postgresql_where=text("delivered_at IS NULL")),
        Index('idx_nda_events_nda_id', 'nda_id'),
        Index('idx_nda_events_scheduled_for', 'scheduled_for'),
        UniqueConstraint('nda_id', 'kind', 'scheduled_for', name='uq_nda_event_dedupe'),
    )


# User Management Tables

class User(Base):
    """
    User accounts for authentication and authorization.
    """
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)  # bcrypt hash
    role = Column(String(20), nullable=False, default="user")  # "admin", "usermgt", "user"
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_users_username', 'username'),
        Index('idx_users_role', 'role'),
        Index('idx_users_active', 'is_active'),
    )


# Workflow Automation Tables

class NDATemplate(Base):
    """
    NDA template definitions for generating unsigned NDAs.
    Supports versioning - each template can have multiple versions.
    """
    __tablename__ = "nda_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String(512), nullable=False)  # Path in MinIO/S3
    version = Column(Integer, nullable=False, default=1)  # Template version number
    template_key = Column(String(255), nullable=False)  # Unique key for grouping versions (e.g., "standard-nda")
    is_active = Column(Boolean, nullable=False, default=True)
    is_current = Column(Boolean, nullable=False, default=True)  # True for the latest version
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    change_notes = Column(Text, nullable=True)  # Notes about what changed in this version

    __table_args__ = (
        Index('idx_templates_name', 'name'),
        Index('idx_templates_key', 'template_key'),
        Index('idx_templates_active', 'is_active'),
        Index('idx_templates_current', 'is_current'),
        Index('idx_templates_created_at', 'created_at'),
        UniqueConstraint('template_key', 'version', name='uq_template_key_version'),
    )


class NDAWorkflowInstance(Base):
    """
    Track Camunda workflow instances for NDA review and approval.
    """
    __tablename__ = "nda_workflow_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nda_record_id = Column(UUID(as_uuid=True), ForeignKey("nda_records.id"), nullable=False, unique=True)
    camunda_process_instance_id = Column(String(100), nullable=False, unique=True)
    current_status = Column(String(50), nullable=False)  # e.g., "llm_review", "human_review", "approval"
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_workflow_instances_nda_record', 'nda_record_id'),
        Index('idx_workflow_instances_camunda_id', 'camunda_process_instance_id'),
        Index('idx_workflow_instances_status', 'current_status'),
        Index('idx_workflow_instances_started_at', 'started_at'),
    )


class NDAWorkflowTask(Base):
    """
    Track workflow tasks for assignment and completion.
    """
    __tablename__ = "nda_workflow_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_instance_id = Column(UUID(as_uuid=True), ForeignKey("nda_workflow_instances.id"), nullable=False)
    task_id = Column(String(100), nullable=False)  # Camunda task ID
    task_name = Column(String(255), nullable=False)  # Human-readable task name
    assignee_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # "pending", "assigned", "completed", "rejected"
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_workflow_tasks_instance', 'workflow_instance_id'),
        Index('idx_workflow_tasks_task_id', 'task_id'),
        Index('idx_workflow_tasks_assignee', 'assignee_user_id'),
        Index('idx_workflow_tasks_status', 'status'),
        Index('idx_workflow_tasks_due_date', 'due_date'),
        UniqueConstraint('task_id', name='uq_workflow_tasks_task_id'),
    )


class EmailConfig(Base):
    """
    Email server configuration for sending and receiving emails.
    """
    __tablename__ = "email_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)  # Configuration name
    smtp_host = Column(String(255), nullable=False)
    smtp_port = Column(Integer, nullable=False, default=587)
    smtp_user = Column(String(255), nullable=False)
    smtp_password_encrypted = Column(String(512), nullable=False)  # Encrypted password
    smtp_use_tls = Column(Boolean, nullable=False, default=True)
    imap_host = Column(String(255), nullable=True)
    imap_port = Column(Integer, nullable=True, default=993)
    imap_user = Column(String(255), nullable=True)
    imap_password_encrypted = Column(String(512), nullable=True)  # Encrypted password
    imap_use_ssl = Column(Boolean, nullable=True, default=True)
    from_address = Column(String(255), nullable=False)
    from_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_email_config_name', 'name'),
        Index('idx_email_config_active', 'is_active'),
    )


class WorkflowConfig(Base):
    """
    Workflow configuration for reviewers, approvers, and settings.
    """
    __tablename__ = "workflow_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)  # Configuration name
    reviewer_user_ids = Column(JSON, nullable=False, default=list)  # Array of user UUIDs
    approver_user_ids = Column(JSON, nullable=False, default=list)  # Array of user UUIDs
    final_approver_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    llm_review_enabled = Column(Boolean, nullable=False, default=True)
    llm_review_threshold = Column(Float, nullable=True, default=0.7)  # Confidence threshold
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_workflow_config_name', 'name'),
        Index('idx_workflow_config_active', 'is_active'),
    )


class EmailMessage(Base):
    """
    Track sent and received emails related to NDAs.
    """
    __tablename__ = "email_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nda_record_id = Column(UUID(as_uuid=True), ForeignKey("nda_records.id"), nullable=True)
    message_id = Column(String(255), nullable=False, unique=True)  # Email Message-ID header
    direction = Column(String(20), nullable=False)  # "sent" or "received"
    subject = Column(String(512), nullable=False)
    body = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    from_address = Column(String(255), nullable=False)
    to_addresses = Column(JSON, nullable=False)  # Array of email addresses
    cc_addresses = Column(JSON, nullable=True)  # Array of email addresses
    attachments = Column(JSON, nullable=True)  # Array of attachment metadata
    tracking_id = Column(String(100), nullable=True)  # For linking emails to NDAs
    sent_at = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_email_messages_nda_record', 'nda_record_id'),
        Index('idx_email_messages_message_id', 'message_id'),
        Index('idx_email_messages_direction', 'direction'),
        Index('idx_email_messages_tracking_id', 'tracking_id'),
        Index('idx_email_messages_sent_at', 'sent_at'),
        Index('idx_email_messages_received_at', 'received_at'),
    )


class NDAAuditLog(Base):
    """
    Audit trail for all NDA actions and status changes.
    """
    __tablename__ = "nda_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nda_record_id = Column(UUID(as_uuid=True), ForeignKey("nda_records.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., "status_changed", "email_sent", "workflow_started"
    details = Column(JSON, nullable=True)  # Additional action details
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(512), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_audit_log_nda_record', 'nda_record_id'),
        Index('idx_audit_log_user', 'user_id'),
        Index('idx_audit_log_action', 'action'),
        Index('idx_audit_log_timestamp', 'timestamp'),
    )


# ---------- Postgres helpers: extensions, triggers ----------

# pgcrypto and pg_trgm extensions are created in migrations.

_nda_tsv_function = DDL(
    """
    CREATE OR REPLACE FUNCTION nda_set_tsv()
    RETURNS trigger AS $$
    BEGIN
        NEW.text_tsv :=
            to_tsvector(
                'english',
                coalesce(NEW.extracted_text, '') || ' ' || coalesce(NEW.counterparty_name, '')
            );
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
).execute_if(dialect='postgresql')

_nda_tsv_trigger = DDL(
    """
    CREATE TRIGGER nda_tsv_trg
    BEFORE INSERT OR UPDATE OF extracted_text, counterparty_name
    ON nda_records
    FOR EACH ROW EXECUTE FUNCTION nda_set_tsv();
    """
).execute_if(dialect='postgresql')

_nda_tsv_drop_trigger = DDL(
    "DROP TRIGGER IF EXISTS nda_tsv_trg ON nda_records;"
).execute_if(dialect='postgresql')

_nda_tsv_drop_function = DDL(
    "DROP FUNCTION IF EXISTS nda_set_tsv();"
).execute_if(dialect='postgresql')

event.listen(NDARecord.__table__, 'after_create', _nda_tsv_function)
event.listen(NDARecord.__table__, 'after_create', _nda_tsv_trigger)
event.listen(NDARecord.__table__, 'before_drop', _nda_tsv_drop_trigger)
event.listen(NDARecord.__table__, 'after_drop', _nda_tsv_drop_function)
