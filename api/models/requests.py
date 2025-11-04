"""
Pydantic models for API requests
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(..., description="Search query text")
    k: int = Field(default=50, description="Number of results to return")
    filters: Optional[Dict] = Field(default=None, description="Optional filters (party, date_range, governing_law, is_mutual)")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is the confidentiality period?",
                "k": 50,
                "filters": {
                    "party": "Acme Corp",
                    "is_mutual": True
                }
            }
        }


class AnswerRequest(BaseModel):
    """Answer request model"""
    question: str = Field(..., description="Question to answer")
    filters: Optional[Dict] = Field(default=None, description="Optional filters")
    max_context_chunks: int = Field(default=10, description="Maximum context chunks to use")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What information is considered confidential?",
                "filters": {
                    "party": "Acme Corp"
                },
                "max_context_chunks": 10
            }
        }


class UploadRequest(BaseModel):
    """Upload request metadata"""
    filename: Optional[str] = Field(None, description="Optional filename override")


class CompetencyQuestionCreate(BaseModel):
    """Create competency question"""
    question_text: str
    category_id: Optional[str] = None
    expected_clause_id: Optional[str] = None
    expected_answer_text: Optional[str] = None


class TestRunRequest(BaseModel):
    """Run competency test"""
    question_id: str
    document_id: Optional[str] = None  # If None, test against all documents


class TestFeedbackRequest(BaseModel):
    """Feedback on test result"""
    test_run_id: str
    user_feedback: str = Field(..., pattern="^(correct|incorrect)$")
    feedback_text: Optional[str] = None
