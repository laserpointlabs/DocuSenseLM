"""
Pydantic models for API responses
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


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
