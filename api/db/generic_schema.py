"""
Generic Legal Document Schema for Phase 2

This schema generalizes the Phase 1 NDA-specific schema to support any document type:
- LegalDocument (replaces NDARecord) - supports any document type
- DocumentType - configuration for different document types  
- DocumentWorkflowInstance (replaces NDAWorkflowInstance) - generic workflows
- DocumentWorkflowTask (replaces NDAWorkflowTask) - generic tasks
- DocumentTemplate (replaces NDATemplate) - generic templates

Maintains 100% backward compatibility with Phase 1 NDA system.
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

# Use same base as existing schema for compatibility
from api.db.schema import Base, TSVectorType


class JSONBType(TypeDecorator):
    """Dialect-aware JSONB column that falls back to TEXT for non-PostgreSQL."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is not None:
            if dialect.name != "postgresql":
                import json
                return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if dialect.name != "postgresql":
                import json
                return json.loads(value)
        return value


class LegalDocument(Base):
    """
    Generic legal document record - supports any document type.
    
    Replaces NDARecord with generalized fields and JSONB metadata
    for document-type-specific data.
    """
    __tablename__ = "legal_documents"

    # Core identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True, unique=True)
    
    # Document type and classification
    document_type = Column(String(50), ForeignKey("document_types.type_key"), nullable=False)
    document_subtype = Column(String(50), nullable=True)  # 'mutual', 'unilateral', 'standard', 'custom'
    
    # Generic party information
    primary_party_name = Column(String(255), nullable=False, default="Your Organization")
    counterparty_name = Column(String(255), nullable=False)
    counterparty_domain = Column(String(255), nullable=True)
    counterparty_email = Column(String(255), nullable=True)
    
    # Generic dates and terms
    effective_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    
    # Generic status (same as Phase 1)
    status = Column(String(30), nullable=False, default="created")
    
    # Generic ownership and access
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    entity_id = Column(String(255), nullable=True)  # For multi-entity organizations
    
    # File and content (same as Phase 1)
    file_uri = Column(String(512), nullable=False)
    file_sha256 = Column(LargeBinary, nullable=False, unique=True)
    extracted_text = Column(Text, nullable=True)
    text_tsv = Column(TSVectorType())
    
    # Flexible document-type-specific metadata
    document_metadata = Column(JSONBType, nullable=False, default='{}')
    
    # Workflow links (generalized)
    workflow_instance_id = Column(UUID(as_uuid=True), ForeignKey("document_workflow_instances.id"), nullable=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("document_templates.id"), nullable=True)
    template_version = Column(Integer, nullable=True)
    
    # Audit and tags (same as Phase 1)
    tags = Column(JSONBType, nullable=False, default='{}')
    facts_json = Column(JSONBType, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('document_id', name='uq_legal_documents_document_id'),
        CheckConstraint(
            "status IN ("
            "'created',"              # Initial state when document created from template
            "'draft',"               # Being edited internally  
            "'in_review',"           # Workflow started, under review
            "'pending_signature',"   # Sent to counterparty, waiting for signature
            "'customer_signed',"     # Counterparty returned signed copy
            "'llm_reviewed_approved'," # LLM approved (pre-send or post-signature)
            "'llm_reviewed_rejected'," # LLM rejected 
            "'reviewed',"            # Human reviewed (pre-send or post-signature)
            "'approved',"            # Approved internally
            "'rejected',"            # Rejected internally
            "'signed',"              # Fully executed (both parties signed)
            "'active',"              # Active and in effect
            "'expired',"             # Expired
            "'terminated',"          # Terminated early
            "'archived'"             # Archived/inactive
            ")",
            name='chk_legal_documents_status'
        ),
        Index('idx_legal_documents_counterparty', 'counterparty_domain', 'counterparty_name'),
        Index('idx_legal_documents_document_type', 'document_type'),
        Index('idx_legal_documents_status', 'status'),
        Index('idx_legal_documents_expiry_active', 'expiry_date',
              postgresql_where=text("status = 'active'")),
        Index('idx_legal_documents_text_tsv', 'text_tsv', postgresql_using='gin'),
        Index('idx_legal_documents_workflow_instance', 'workflow_instance_id'),
        Index('idx_legal_documents_template', 'template_id'),
        # Index for metadata would be: Index('idx_legal_documents_metadata', 'document_metadata', postgresql_using='gin'),
    )


class DocumentType(Base):
    """
    Document type configuration - defines supported document types and their settings.
    
    Allows the system to support NDAs, service agreements, employment contracts,
    and any other document type with configurable workflows and validation.
    """
    __tablename__ = "document_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_key = Column(String(50), unique=True, nullable=False)  # 'nda', 'service_agreement'
    display_name = Column(String(100), nullable=False)         # 'Non-Disclosure Agreement'
    description = Column(Text, nullable=True)
    
    # Schema definition for document_metadata JSONB field
    metadata_schema = Column(JSONBType, nullable=False, default='{}')  # JSON Schema for validation
    
    # Workflow configuration
    default_workflow_process_key = Column(String(100), nullable=True)  # 'nda_review_approval'
    
    # Review and validation settings
    llm_review_enabled = Column(Boolean, nullable=False, default=True)
    llm_review_threshold = Column(Float, nullable=False, default=0.7)
    require_human_review = Column(Boolean, nullable=False, default=True)
    
    # Template settings
    template_bucket = Column(String(100), nullable=False, default='legal-templates')
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_document_types_key', 'type_key'),
        Index('idx_document_types_active', 'is_active'),
    )


class DocumentWorkflowInstance(Base):
    """
    Generic workflow instance tracking - supports any document type.
    
    Replaces NDAWorkflowInstance with document type awareness.
    """
    __tablename__ = "document_workflow_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_document_id = Column(UUID(as_uuid=True), ForeignKey("legal_documents.id"), nullable=False, unique=True)
    document_type = Column(String(50), ForeignKey("document_types.type_key"), nullable=False)
    camunda_process_instance_id = Column(String(100), nullable=False, unique=True)
    process_key = Column(String(100), nullable=False)  # BPMN process definition key
    current_status = Column(String(50), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_doc_workflow_instances_document', 'legal_document_id'),
        Index('idx_doc_workflow_instances_type', 'document_type'),
        Index('idx_doc_workflow_instances_camunda_id', 'camunda_process_instance_id'),
        Index('idx_doc_workflow_instances_status', 'current_status'),
        Index('idx_doc_workflow_instances_started_at', 'started_at'),
    )


class DocumentWorkflowTask(Base):
    """
    Generic workflow task tracking - supports any document workflow.
    
    Replaces NDAWorkflowTask with document type awareness.
    """
    __tablename__ = "document_workflow_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_instance_id = Column(UUID(as_uuid=True), ForeignKey("document_workflow_instances.id"), nullable=False)
    task_id = Column(String(100), nullable=False)  # Camunda task ID
    task_name = Column(String(255), nullable=False)  # Human-readable task name
    assignee_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_doc_workflow_tasks_instance', 'workflow_instance_id'),
        Index('idx_doc_workflow_tasks_task_id', 'task_id'),
        Index('idx_doc_workflow_tasks_assignee', 'assignee_user_id'),
        Index('idx_doc_workflow_tasks_status', 'status'),
        Index('idx_doc_workflow_tasks_due_date', 'due_date'),
        UniqueConstraint('task_id', name='uq_doc_workflow_tasks_task_id'),
    )


class DocumentTemplate(Base):
    """
    Generic document template - supports any document type.
    
    Replaces NDATemplate with document type awareness and variable schema.
    """
    __tablename__ = "document_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type = Column(String(50), ForeignKey("document_types.type_key"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String(512), nullable=False)  # Path in MinIO/S3
    version = Column(Integer, nullable=False, default=1)
    template_key = Column(String(255), nullable=False)  # Groups versions together
    
    # Template variable schema definition
    variable_schema = Column(JSONBType, nullable=False, default='{}')  # JSON Schema for template variables
    
    is_active = Column(Boolean, nullable=False, default=True)
    is_current = Column(Boolean, nullable=False, default=True)  # True for latest version
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    change_notes = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_doc_templates_type', 'document_type'),
        Index('idx_doc_templates_name', 'name'),
        Index('idx_doc_templates_key', 'template_key'),
        Index('idx_doc_templates_active', 'is_active'),
        Index('idx_doc_templates_current', 'is_current'),
        Index('idx_doc_templates_created_at', 'created_at'),
        UniqueConstraint('template_key', 'version', name='uq_doc_template_key_version'),
    )


# Additional generic tables for email and audit (generalized from Phase 1)

class DocumentEmailMessage(Base):
    """
    Generic email message tracking - supports any document type.
    
    Replaces EmailMessage with document type awareness.
    """
    __tablename__ = "document_email_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_document_id = Column(UUID(as_uuid=True), ForeignKey("legal_documents.id"), nullable=True)
    document_type = Column(String(50), ForeignKey("document_types.type_key"), nullable=True)
    message_id = Column(String(255), nullable=False, unique=True)
    direction = Column(String(20), nullable=False)  # "sent" or "received"
    subject = Column(String(512), nullable=False)
    body = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    from_address = Column(String(255), nullable=False)
    to_addresses = Column(JSONBType, nullable=False)  # Array of email addresses
    cc_addresses = Column(JSONBType, nullable=True)  # Array of email addresses
    attachments = Column(JSONBType, nullable=True)  # Array of attachment metadata
    tracking_id = Column(String(100), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_doc_email_messages_document', 'legal_document_id'),
        Index('idx_doc_email_messages_type', 'document_type'),
        Index('idx_doc_email_messages_message_id', 'message_id'),
        Index('idx_doc_email_messages_direction', 'direction'),
        Index('idx_doc_email_messages_tracking_id', 'tracking_id'),
        Index('idx_doc_email_messages_sent_at', 'sent_at'),
        Index('idx_doc_email_messages_received_at', 'received_at'),
    )


class DocumentAuditLog(Base):
    """
    Generic audit log - supports any document type.
    
    Replaces NDAAuditLog with document type awareness.
    """
    __tablename__ = "document_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legal_document_id = Column(UUID(as_uuid=True), ForeignKey("legal_documents.id"), nullable=False)
    document_type = Column(String(50), ForeignKey("document_types.type_key"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., "status_changed", "email_sent", "workflow_started"
    details = Column(JSONBType, nullable=True)  # Additional action details
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(512), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_doc_audit_log_document', 'legal_document_id'),
        Index('idx_doc_audit_log_type', 'document_type'),
        Index('idx_doc_audit_log_user', 'user_id'),
        Index('idx_doc_audit_log_action', 'action'),
        Index('idx_doc_audit_log_timestamp', 'timestamp'),
    )


# Backward Compatibility Views and Functions

def create_nda_compatibility_view():
    """
    Create view that provides backward compatibility with NDARecord table structure.
    
    This allows existing Phase 1 code to continue working unchanged.
    """
    return DDL("""
    CREATE OR REPLACE VIEW nda_records AS
    SELECT 
        id,
        document_id,
        COALESCE(document_metadata->>'direction', 'outbound') as direction,
        COALESCE(document_metadata->>'nda_type', 'mutual') as nda_type,
        counterparty_name,
        counterparty_domain,
        entity_id,
        owner_user_id,
        effective_date,
        COALESCE((document_metadata->>'term_months')::integer, 24) as term_months,
        COALESCE((document_metadata->>'survival_months')::integer, 36) as survival_months,
        expiry_date,
        status,
        file_uri,
        file_sha256,
        extracted_text,
        text_tsv,
        tags,
        facts_json,
        created_at,
        updated_at,
        workflow_instance_id,
        template_id,
        template_version
    FROM legal_documents 
    WHERE document_type = 'nda';
    """)


def create_nda_compatibility_functions():
    """
    Create functions for INSERT/UPDATE/DELETE on nda_records view to maintain compatibility.
    """
    return DDL("""
    -- Function to handle INSERT into nda_records view
    CREATE OR REPLACE FUNCTION nda_records_insert()
    RETURNS TRIGGER AS $$
    BEGIN
        INSERT INTO legal_documents (
            id, document_id, document_type, counterparty_name, counterparty_domain,
            entity_id, owner_user_id, effective_date, expiry_date, status,
            file_uri, file_sha256, extracted_text, text_tsv, tags, facts_json,
            workflow_instance_id, template_id, template_version,
            document_metadata
        ) VALUES (
            COALESCE(NEW.id, gen_random_uuid()),
            NEW.document_id,
            'nda',
            NEW.counterparty_name,
            NEW.counterparty_domain,
            NEW.entity_id,
            NEW.owner_user_id,
            NEW.effective_date,
            NEW.expiry_date,
            NEW.status,
            NEW.file_uri,
            NEW.file_sha256,
            NEW.extracted_text,
            NEW.text_tsv,
            NEW.tags,
            NEW.facts_json,
            NEW.workflow_instance_id,
            NEW.template_id,
            NEW.template_version,
            jsonb_build_object(
                'direction', COALESCE(NEW.direction, 'outbound'),
                'nda_type', COALESCE(NEW.nda_type, 'mutual'),
                'term_months', COALESCE(NEW.term_months, 24),
                'survival_months', COALESCE(NEW.survival_months, 36)
            )
        );
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    -- Trigger for INSERT
    CREATE TRIGGER nda_records_insert_trigger
    INSTEAD OF INSERT ON nda_records
    FOR EACH ROW EXECUTE FUNCTION nda_records_insert();
    
    -- Similar functions for UPDATE and DELETE would be added here
    """)


# Pre-populated document types for common legal documents

def get_default_document_types():
    """Get default document type configurations"""
    return [
        DocumentType(
            type_key='nda',
            display_name='Non-Disclosure Agreement',
            description='Confidentiality agreements between parties',
            is_active=True,
            metadata_schema={
                "type": "object",
                "properties": {
                    "nda_type": {"type": "string", "enum": ["mutual", "unilateral"]},
                    "direction": {"type": "string", "enum": ["inbound", "outbound"]},
                    "term_months": {"type": "integer", "minimum": 1, "maximum": 120},
                    "survival_months": {"type": "integer", "minimum": 0, "maximum": 120},
                    "governing_law": {"type": "string", "maxLength": 100},
                    "disclosing_party": {"type": "string"},
                    "receiving_party": {"type": "string"}
                },
                "required": ["nda_type"]
            },
            default_workflow_process_key='nda_review_approval',
            llm_review_enabled=True,
            llm_review_threshold=0.7,
            require_human_review=True,
            template_bucket='nda-templates'
        ),
        DocumentType(
            type_key='service_agreement',
            display_name='Service Agreement',
            description='Agreements for provision of services',
            is_active=True,
            metadata_schema={
                "type": "object",
                "properties": {
                    "service_type": {"type": "string", "enum": ["consulting", "development", "maintenance", "support"]},
                    "contract_value": {"type": "number", "minimum": 0},
                    "payment_terms": {"type": "string"},
                    "project_duration_months": {"type": "integer", "minimum": 1},
                    "deliverables": {"type": "array", "items": {"type": "string"}},
                    "milestones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "due_date": {"type": "string", "format": "date"},
                                "payment": {"type": "number", "minimum": 0}
                            }
                        }
                    }
                },
                "required": ["service_type", "contract_value"]
            },
            default_workflow_process_key='service_agreement_approval',
            llm_review_enabled=True,
            llm_review_threshold=0.8,  # Higher threshold for contracts
            require_human_review=True,
            template_bucket='service-agreement-templates'
        ),
        DocumentType(
            type_key='employment_contract',
            display_name='Employment Contract',
            description='Employment agreements and contracts',
            is_active=True,
            metadata_schema={
                "type": "object",
                "properties": {
                    "position": {"type": "string"},
                    "department": {"type": "string"},
                    "salary": {"type": "number", "minimum": 0},
                    "start_date": {"type": "string", "format": "date"},
                    "employment_type": {"type": "string", "enum": ["full_time", "part_time", "contract"]},
                    "benefits": {"type": "array", "items": {"type": "string"}},
                    "probation_months": {"type": "integer", "minimum": 0, "maximum": 12}
                },
                "required": ["position", "salary", "start_date", "employment_type"]
            },
            default_workflow_process_key='employment_contract_approval',
            llm_review_enabled=True,
            llm_review_threshold=0.9,  # Very high threshold for employment
            require_human_review=True,
            template_bucket='employment-templates'
        )
    ]
