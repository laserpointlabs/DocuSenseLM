"""
Pydantic models for API responses
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


class SearchResult(BaseModel):
    """Search result model"""
    chunk_id: str
    score: float
    text: str
    doc_id: str
    section_type: str
    clause_number: Optional[str]
    page_num: int
    span_start: int
    span_end: int
    source_uri: str


class SearchResponse(BaseModel):
    """Search response"""
    results: List[SearchResult]
    total: int
    query: str


class Citation(BaseModel):
    """Citation model"""
    doc_id: str
    clause_number: Optional[str]
    page_num: int
    span_start: int
    span_end: int
    source_uri: str
    excerpt: str


class AnswerResponse(BaseModel):
    """Answer response"""
    answer: str
    citations: List[Citation]
    question: str
    confidence: Optional[float] = None  # Confidence score (0.0 to 1.0)
    evaluation_reasoning: Optional[str] = None  # Optional reasoning for confidence score


class DocumentResponse(BaseModel):
    """Document response"""
    id: str
    filename: str
    upload_date: datetime
    status: str
    metadata: Optional[Dict] = None


class DocumentListResponse(BaseModel):
    """List of documents"""
    documents: List[DocumentResponse]
    total: int


class UploadResponse(BaseModel):
    """Upload response"""
    document_id: str
    filename: str
    status: str
    message: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    services: Dict[str, str]
    timestamp: datetime


class StatsResponse(BaseModel):
    """Statistics response"""
    total_documents: int
    total_chunks: int
    total_questions: int
    indexed_documents: int
    opensearch_status: str
    qdrant_status: str


class NDARecordSummary(BaseModel):
    """Summary of an NDA registry entry."""
    id: str
    document_id: Optional[str]
    counterparty_name: str
    counterparty_domain: Optional[str]
    status: str
    direction: Optional[str]
    nda_type: Optional[str]
    entity_id: Optional[str]
    owner_user_id: Optional[str]
    effective_date: Optional[date]
    expiry_date: Optional[date]
    term_months: Optional[int]
    survival_months: Optional[int]
    tags: Dict[str, Any] = Field(default_factory=dict)
    file_uri: str


class NDARegistryResponse(BaseModel):
    """NDA registry search response."""
    results: List[NDARecordSummary]
    total: int


class ActiveNDAMatch(BaseModel):
    """Match returned from active NDA check."""
    id: str
    counterparty_name: str
    counterparty_domain: Optional[str]
    effective_date: Optional[date]
    expiry_date: Optional[date]
    status: str
    file_uri: str


class ActiveNDAResponse(BaseModel):
    """Active NDA lookup response."""
    query: str
    as_of: date
    active: bool
    matches: List[ActiveNDAMatch]


class NDAEventResponse(BaseModel):
    """Event payload returned to clients."""
    id: int
    nda_id: str
    kind: str
    scheduled_for: datetime
    delivered_at: Optional[datetime]
    payload: Dict[str, Any] = Field(default_factory=dict)


# Template Management Responses

class TemplateResponse(BaseModel):
    """Template response"""
    id: str
    name: str
    description: Optional[str] = None
    file_path: str
    version: int
    template_key: str
    is_active: bool
    is_current: bool
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    change_notes: Optional[str] = None


class TemplateListResponse(BaseModel):
    """List of templates"""
    templates: List[TemplateResponse]
    total: int


class TemplateRenderResponse(BaseModel):
    """Template render response"""
    file_data: str  # Base64 encoded DOCX file
    filename: str


# NDA Workflow Responses

class NDARecordSummary(BaseModel):
    """NDA record summary"""
    id: str
    counterparty_name: str
    counterparty_domain: Optional[str] = None
    status: str
    effective_date: Optional[date] = None
    term_months: Optional[int] = None
    survival_months: Optional[int] = None
    expiry_date: Optional[date] = None
    tags: Dict[str, Any] = {}
    file_uri: str
    workflow_instance_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WorkflowInstanceResponse(BaseModel):
    """Workflow instance response"""
    id: str
    nda_record_id: str
    camunda_process_instance_id: str
    current_status: str
    started_at: datetime
    completed_at: Optional[datetime] = None


class WorkflowTaskResponse(BaseModel):
    """Workflow task response"""
    id: str
    task_id: str
    task_name: str
    status: str
    assignee_user_id: Optional[str] = None
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    comments: Optional[str] = None


class WorkflowStatusResponse(BaseModel):
    """NDA workflow status response"""
    nda_id: str
    status: str
    workflow_status: Optional[str] = None
    workflow_instance_id: Optional[str] = None
    current_tasks: List[WorkflowTaskResponse] = []
    progress_percentage: Optional[float] = None


class EmailSendResponse(BaseModel):
    """Email send response"""
    message_id: str
    tracking_id: str
    sent_to: List[str]
    status: str
