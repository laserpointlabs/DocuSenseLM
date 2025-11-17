from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date, datetime


class SearchRequest(BaseModel):
    """Search request"""
    query: str
    k: Optional[int] = 50
    filters: Optional[dict] = None


class AnswerRequest(BaseModel):
    """Answer request"""
    question: str
    document_id: Optional[str] = None
    filters: Optional[dict] = None
    max_context_chunks: Optional[int] = 30


class UploadRequest(BaseModel):
    """Upload request"""
    filename: str
    content_type: str


class CompetencyQuestionCreate(BaseModel):
    """Create competency question"""
    question_text: str
    category_id: Optional[str] = None
    document_id: Optional[str] = None  # Associate with specific document
    verification_hint: Optional[str] = None  # How to verify the answer
    expected_clause: Optional[str] = None  # Expected clause title/number
    expected_page: Optional[int] = None  # Expected page for verification
    expected_clause_id: Optional[str] = None
    expected_answer_text: Optional[str] = None
    confidence_threshold: Optional[float] = 0.7


class CompetencyQuestionUpdate(BaseModel):
    """Update competency question"""
    question_text: Optional[str] = None
    category_id: Optional[str] = None
    document_id: Optional[str] = None
    verification_hint: Optional[str] = None
    expected_clause: Optional[str] = None
    expected_page: Optional[int] = None
    expected_answer_text: Optional[str] = None
    confidence_threshold: Optional[float] = None
    is_active: Optional[bool] = None


class TestRunRequest(BaseModel):
    """Run competency test"""
    question_id: str
    document_id: Optional[str] = None  # If None, test against all documents


class TestFeedbackRequest(BaseModel):
    """Provide feedback on test result"""
    test_run_id: str
    feedback_type: str  # "correct", "incorrect", "partial"
    notes: Optional[str] = None


# Template Management Requests

class TemplateCreateRequest(BaseModel):
    """Create template request"""
    name: str
    description: Optional[str] = None
    template_key: Optional[str] = None
    change_notes: Optional[str] = None


class TemplateRenderRequest(BaseModel):
    """Render template request"""
    data: Dict[str, Any]  # Template variable values


# NDA Workflow Requests

class NDACreateRequest(BaseModel):
    """Create NDA from template request"""
    template_id: str
    counterparty_name: str
    counterparty_domain: Optional[str] = None
    counterparty_email: Optional[str] = None
    disclosing_party: Optional[str] = None
    receiving_party: Optional[str] = None
    effective_date: Optional[date] = None
    term_months: Optional[int] = None
    survival_months: Optional[int] = None
    governing_law: Optional[str] = None
    direction: Optional[str] = None  # "inbound" or "outbound"
    nda_type: Optional[str] = None  # "mutual" or "unilateral"
    entity_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None  # Additional template variables
    
    # Workflow options
    auto_start_workflow: bool = True  # Automatically start workflow after creation
    reviewer_user_id: Optional[str] = None
    approver_user_id: Optional[str] = None
    internal_signer_user_id: Optional[str] = None


class NDASendEmailRequest(BaseModel):
    """Send NDA email request"""
    to_addresses: List[str]
    cc_addresses: Optional[List[str]] = None
    subject: Optional[str] = None
    message: Optional[str] = None


class WorkflowStartRequest(BaseModel):
    """Start workflow request"""
    reviewer_user_id: Optional[str] = None
    approver_user_id: Optional[str] = None
    internal_signer_user_id: Optional[str] = None


class TaskCompleteRequest(BaseModel):
    """Complete task request"""
    approved: bool
    comments: Optional[str] = None
