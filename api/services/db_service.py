"""
Database service for document queries
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from api.db.schema import (
    Document, DocumentChunk, Party, DocumentMetadata,
    CompetencyQuestion, QuestionCategory, TestRun, TestFeedback,
    DocumentStatus
)
from api.models.responses import DocumentResponse


class DBService:
    """Database query service"""

    def get_document(self, db: Session, document_id: str) -> Optional[Document]:
        """Get document by ID"""
        return db.query(Document).filter(Document.id == document_id).first()

    def list_documents(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Document], int]:
        """List documents with pagination"""
        total = db.query(func.count(Document.id)).scalar()
        documents = db.query(Document).offset(skip).limit(limit).all()
        return documents, total

    def get_document_chunks(
        self,
        db: Session,
        document_id: str
    ) -> List[DocumentChunk]:
        """Get all chunks for a document"""
        return db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).order_by(DocumentChunk.chunk_index).all()

    def get_document_metadata(
        self,
        db: Session,
        document_id: str
    ) -> Optional[DocumentMetadata]:
        """Get document metadata"""
        return db.query(DocumentMetadata).filter(
            DocumentMetadata.document_id == document_id
        ).first()

    def get_parties(
        self,
        db: Session,
        document_id: str
    ) -> List[Party]:
        """Get parties for a document"""
        return db.query(Party).filter(Party.document_id == document_id).all()

    def get_stats(self, db: Session) -> dict:
        """Get system statistics"""
        total_documents = db.query(func.count(Document.id)).scalar()
        total_chunks = db.query(func.count(DocumentChunk.id)).scalar()
        total_questions = db.query(func.count(CompetencyQuestion.id)).scalar()

        indexed_documents = db.query(func.count(Document.id)).filter(
            Document.status == DocumentStatus.PROCESSED
        ).scalar()

        return {
            'total_documents': total_documents or 0,
            'total_chunks': total_chunks or 0,
            'total_questions': total_questions or 0,
            'indexed_documents': indexed_documents or 0
        }

    def get_competency_questions(
        self,
        db: Session,
        category_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[CompetencyQuestion], int]:
        """List competency questions"""
        query = db.query(CompetencyQuestion).filter(
            CompetencyQuestion.is_active == True
        )

        if category_id:
            query = query.filter(CompetencyQuestion.category_id == category_id)

        total = query.count()
        questions = query.offset(skip).limit(limit).all()
        return questions, total

    def create_competency_question(
        self,
        db: Session,
        question_text: str,
        category_id: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> CompetencyQuestion:
        """Create a new competency question"""
        question = CompetencyQuestion(
            question_text=question_text,
            category_id=category_id,
            created_by=created_by
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        return question


# Global service instance
db_service = DBService()
