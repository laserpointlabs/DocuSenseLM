from pydantic import BaseModel
from typing import Optional


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
