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
    workflow_instance_id: Optional[str] = None  # Workflow instance ID if workflow is started


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


class TemplateResponse(BaseModel):
    """Template response"""
    id: str
    name: str
    description: Optional[str]
    file_path: str
    is_active: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    version: Optional[int] = 1
    template_key: Optional[str] = None
    is_current: Optional[bool] = True
    change_notes: Optional[str] = None


class TemplateListResponse(BaseModel):
    """List of templates"""
    templates: List[TemplateResponse]
    total: int


class TemplateRenderResponse(BaseModel):
    """Template render response"""
    file_data: str  # Base64 encoded DOCX file
    filename: str


class NDAEventResponse(BaseModel):
    """Event payload returned to clients."""
    id: int
    nda_id: str
    kind: str
    scheduled_for: datetime
    delivered_at: Optional[datetime]
    payload: Dict[str, Any] = Field(default_factory=dict)
