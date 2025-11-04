"""
Competency question router
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from api.models.requests import (
    CompetencyQuestionCreate, TestRunRequest, TestFeedbackRequest
)
from api.services.db_service import db_service
from api.services.answer_service import answer_service
from api.db import get_db_session
from api.db.schema import CompetencyQuestion, TestRun, TestFeedback
from datetime import datetime
import uuid

router = APIRouter(prefix="/competency", tags=["competency"])


@router.post("/questions")
async def create_question(request: CompetencyQuestionCreate):
    """Create a new competency question"""
    db = get_db_session()
    try:
        question = db_service.create_competency_question(
            db=db,
            question_text=request.question_text,
            category_id=request.category_id,
            document_id=request.document_id,
            verification_hint=request.verification_hint,
            expected_clause=request.expected_clause,
            expected_page=request.expected_page,
            created_by=None  # TODO: Get from auth
        )

        # TODO: Create ground truth if provided
        # if request.expected_clause_id or request.expected_answer_text:
        #     ...

        return {
            "id": str(question.id),
            "question_text": question.question_text,
            "category_id": str(question.category_id) if question.category_id else None,
            "document_id": str(question.document_id) if question.document_id else None,
            "verification_hint": question.verification_hint,
            "expected_clause": question.expected_clause,
            "expected_page": question.expected_page,
            "created_at": question.created_at
        }
    finally:
        db.close()


@router.get("/questions")
async def list_questions(
    category_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """List competency questions"""
    db = get_db_session()
    try:
        questions, total = db_service.get_competency_questions(
            db=db,
            category_id=category_id,
            skip=skip,
            limit=limit
        )

        return {
            "questions": [
                {
                    "id": str(q.id),
                    "question_text": q.question_text,
                    "category_id": str(q.category_id) if q.category_id else None,
                    "document_id": str(q.document_id) if q.document_id else None,
                    "verification_hint": q.verification_hint,
                    "expected_clause": q.expected_clause,
                    "expected_page": q.expected_page,
                    "created_at": q.created_at,
                    "version": q.version
                }
                for q in questions
            ],
            "total": total
        }
    finally:
        db.close()


@router.post("/questions/{question_id}/suggest")
async def suggest_ground_truth(question_id: str):
    """LLM-assisted ground truth suggestion"""
    # TODO: Implement LLM-assisted ground truth suggestion
    return {"message": "Not yet implemented"}


@router.post("/test/run")
async def run_test(request: TestRunRequest):
    """Run a competency test"""
    db = get_db_session()
    try:
        # Get question
        question = db.query(CompetencyQuestion).filter(
            CompetencyQuestion.id == request.question_id
        ).first()

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        # Run answer generation
        # If question has a document_id, prioritize that document
        filters = None
        if request.document_id:
            filters = {"document_id": request.document_id}
        elif question.document_id:
            # Use the question's associated document if no specific document requested
            filters = {"document_id": str(question.document_id)}

        start_time = datetime.now()
        answer_obj = await answer_service.generate_answer(
            question=question.question_text,
            filters=filters
        )
        end_time = datetime.now()

        response_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Calculate accuracy (simplified - would compare to ground truth)
        accuracy_score = None  # TODO: Compare to ground truth

        # Store test run
        test_run = TestRun(
            question_id=request.question_id,
            answer_text=answer_obj.text,
            retrieved_clauses=[c.doc_id for c in answer_obj.citations],
            accuracy_score=accuracy_score,
            response_time_ms=response_time_ms
        )
        db.add(test_run)
        db.commit()
        db.refresh(test_run)

        return {
            "test_run_id": str(test_run.id),
            "question_id": request.question_id,
            "answer": answer_obj.text,
            "citations": [
                {
                    "doc_id": c.doc_id,
                    "clause_number": c.clause_number,
                    "page_num": c.page_num
                }
                for c in answer_obj.citations
            ],
            "accuracy_score": accuracy_score,
            "response_time_ms": response_time_ms,
            "run_at": test_run.run_at
        }
    finally:
        db.close()


@router.post("/test/feedback")
async def submit_feedback(request: TestFeedbackRequest):
    """Submit feedback on test result"""
    db = get_db_session()
    try:
        # Verify test run exists
        test_run = db.query(TestRun).filter(
            TestRun.id == request.test_run_id
        ).first()

        if not test_run:
            raise HTTPException(status_code=404, detail="Test run not found")

        # Create feedback
        feedback = TestFeedback(
            test_run_id=request.test_run_id,
            user_feedback=request.user_feedback,
            feedback_text=request.feedback_text
        )
        db.add(feedback)
        db.commit()

        return {
            "id": str(feedback.id),
            "test_run_id": request.test_run_id,
            "user_feedback": request.user_feedback,
            "feedback_at": feedback.feedback_at
        }
    finally:
        db.close()


@router.get("/test/results")
async def get_test_results(
    question_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """Get test results history"""
    db = get_db_session()
    try:
        query = db.query(TestRun)

        if question_id:
            query = query.filter(TestRun.question_id == question_id)

        total = query.count()
        test_runs = query.order_by(TestRun.run_at.desc()).offset(skip).limit(limit).all()

        return {
            "results": [
                {
                    "id": str(tr.id),
                    "question_id": str(tr.question_id),
                    "run_at": tr.run_at,
                    "answer_text": tr.answer_text,
                    "accuracy_score": tr.accuracy_score,
                    "response_time_ms": tr.response_time_ms
                }
                for tr in test_runs
            ],
            "total": total
        }
    finally:
        db.close()


@router.post("/test/run-all")
async def run_all_tests():
    """Run tests for all active competency questions"""
    db = get_db_session()
    try:
        # Get all active questions
        questions = db.query(CompetencyQuestion).filter(
            CompetencyQuestion.is_active == True
        ).all()

        if not questions:
            return {
                "message": "No active questions found",
                "total": 0,
                "results": []
            }

        results = []
        total_passed = 0
        total_failed = 0

        for question in questions:
            try:
                # Run test for this question
                filters = None
                if question.document_id:
                    filters = {"document_id": str(question.document_id)}

                start_time = datetime.now()
                answer_obj = await answer_service.generate_answer(
                    question=question.question_text,
                    filters=filters
                )
                end_time = datetime.now()

                response_time_ms = int((end_time - start_time).total_seconds() * 1000)

                # Check if test passed (has answer and reasonable response time)
                passed = (
                    answer_obj.text and
                    len(answer_obj.text) > 10 and
                    response_time_ms < 30000  # 30 second timeout
                )

                if passed:
                    total_passed += 1
                else:
                    total_failed += 1

                # Store test run
                test_run = TestRun(
                    question_id=str(question.id),
                    answer_text=answer_obj.text,
                    retrieved_clauses=[c.doc_id for c in answer_obj.citations],
                    accuracy_score=None,
                    response_time_ms=response_time_ms
                )
                db.add(test_run)
                db.commit()
                db.refresh(test_run)

                results.append({
                    "test_run_id": str(test_run.id),
                    "question_id": str(question.id),
                    "question_text": question.question_text,
                    "document_id": str(question.document_id) if question.document_id else None,
                    "passed": passed,
                    "answer": answer_obj.text,
                    "citations_count": len(answer_obj.citations),
                    "response_time_ms": response_time_ms,
                    "run_at": test_run.run_at
                })

            except Exception as e:
                total_failed += 1
                results.append({
                    "question_id": str(question.id),
                    "question_text": question.question_text,
                    "passed": False,
                    "error": str(e)
                })

        return {
            "message": f"Completed testing {len(questions)} questions",
            "total": len(questions),
            "passed": total_passed,
            "failed": total_failed,
            "pass_rate": (total_passed / len(questions) * 100) if questions else 0,
            "results": results
        }
    finally:
        db.close()
