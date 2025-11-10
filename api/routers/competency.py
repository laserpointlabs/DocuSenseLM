"""
Competency question router
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from api.models.requests import (
    CompetencyQuestionCreate, CompetencyQuestionUpdate, TestRunRequest, TestFeedbackRequest
)
from api.services.db_service import db_service
from api.services.answer_service import answer_service
from api.services.answer_evaluator import answer_evaluator
from api.db import get_db_session
from api.db.schema import CompetencyQuestion, TestRun, TestFeedback
from datetime import datetime
import uuid
import os
import logging
import threading

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/competency", tags=["competency"])

# In-memory progress tracking for test runs
_test_progress = {
    "is_running": False,
    "total": 0,
    "completed": 0,
    "current": None,
    "errors": 0,
    "passed": 0,
    "failed": 0
}
_test_progress_lock = threading.Lock()


@router.get("/test/progress")
async def get_test_progress():
    """Get current test run progress"""
    with _test_progress_lock:
        progress = {
            "is_running": _test_progress["is_running"],
            "total": _test_progress["total"],
            "completed": _test_progress["completed"],
            "current": _test_progress["current"],
            "errors": _test_progress["errors"],
            "passed": _test_progress["passed"],
            "failed": _test_progress["failed"],
            "progress_percent": int((_test_progress["completed"] / _test_progress["total"] * 100)) if _test_progress["total"] > 0 else 0
        }
        return progress


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
            expected_answer_text=request.expected_answer_text,
            confidence_threshold=request.confidence_threshold,
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
            "expected_answer_text": question.expected_answer_text,
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
                    "expected_answer_text": q.expected_answer_text,
                    "confidence_threshold": q.confidence_threshold,
                    "created_at": q.created_at,
                    "version": q.version
                }
                for q in questions
            ],
            "total": total
        }
    finally:
        db.close()


@router.put("/questions/{question_id}")
async def update_question(question_id: str, request: CompetencyQuestionUpdate):
    """Update a competency question"""
    db = get_db_session()
    try:
        question = db_service.update_competency_question(
            db=db,
            question_id=question_id,
            question_text=request.question_text,
            category_id=request.category_id,
            document_id=request.document_id,
            verification_hint=request.verification_hint,
            expected_clause=request.expected_clause,
            expected_page=request.expected_page,
            expected_answer_text=request.expected_answer_text,
            confidence_threshold=request.confidence_threshold,
            is_active=request.is_active
        )

        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        return {
            "id": str(question.id),
            "question_text": question.question_text,
            "category_id": str(question.category_id) if question.category_id else None,
            "document_id": str(question.document_id) if question.document_id else None,
            "verification_hint": question.verification_hint,
            "expected_clause": question.expected_clause,
            "expected_page": question.expected_page,
            "expected_answer_text": question.expected_answer_text,
            "confidence_threshold": question.confidence_threshold,
            "is_active": question.is_active,
            "version": question.version,
            "created_at": question.created_at
        }
    finally:
        db.close()


@router.post("/questions/load-from-json")
async def load_questions_from_json(clear_existing: bool = Query(False, description="Clear existing questions before loading")):
    """Load competency questions from eval/qa_pairs.json file"""
    import json
    from pathlib import Path
    
    db = get_db_session()
    try:
        # Find the qa_pairs.json file
        # Try multiple possible locations
        possible_paths = [
            Path("/app/eval/qa_pairs.json"),
            Path("eval/qa_pairs.json"),
            Path(__file__).parent.parent.parent / "eval" / "qa_pairs.json",
        ]
        
        qa_file = None
        for path in possible_paths:
            if path.exists():
                qa_file = path
                break
        
        if not qa_file:
            raise HTTPException(
                status_code=404,
                detail=f"QA pairs file not found. Tried: {[str(p) for p in possible_paths]}"
            )
        
        # Load JSON file
        with open(qa_file, 'r') as f:
            qa_pairs = json.load(f)
        
        # Clear existing questions if requested
        if clear_existing:
            db.query(TestFeedback).delete()
            db.query(TestRun).delete()
            db.query(CompetencyQuestion).delete()
            db.commit()
        
        # Build company name to document ID mapping
        from api.db.schema import Document, DocumentStatus
        import re
        
        company_to_doc = {}
        documents = db.query(Document).filter(Document.status == DocumentStatus.PROCESSED).all()
        
        for doc in documents:
            filename = doc.filename
            if '_Signed NDA' in filename:
                company_full = filename.split('_Signed NDA')[0].strip()
                company_lower = company_full.lower()
                
                # Map full company name
                company_to_doc[company_lower] = str(doc.id)
                
                # Extract short name (remove Inc, Corp, LLC, etc.)
                short_name = re.sub(r'\s+(inc|corp|corporation|llc|ltd|b\.v\.|sdn bhd|company)\.?$', '', company_lower, flags=re.IGNORECASE).strip()
                if short_name and short_name != company_lower:
                    company_to_doc[short_name] = str(doc.id)
                
                # Also map common variations (faunc -> fanuc, etc.)
                if 'fanuc' in company_lower:
                    company_to_doc['faunc'] = str(doc.id)  # Common misspelling
                if 'norris' in company_lower:
                    company_to_doc['norris'] = str(doc.id)
                if 'central coating' in company_lower:
                    company_to_doc['central coating'] = str(doc.id)
                if 'vallen' in company_lower:
                    company_to_doc['vallen'] = str(doc.id)
                if 'kgs' in company_lower:
                    company_to_doc['kgs'] = str(doc.id)
                if 'mcgill' in company_lower:
                    company_to_doc['mcgill'] = str(doc.id)
                if 'unique fire' in company_lower:
                    company_to_doc['unique fire'] = str(doc.id)
                if 'boston green' in company_lower:
                    company_to_doc['boston green'] = str(doc.id)
                if 'shaoxing' in company_lower:
                    company_to_doc['shaoxing'] = str(doc.id)
        
        # Load questions
        loaded_count = 0
        errors = []
        
        for qa in qa_pairs:
            try:
                question_text = qa.get("question", qa.get("question_text", ""))
                if not question_text:
                    continue
                
                # Try to find document_id by matching company names in question
                document_id = None
                question_lower = question_text.lower()
                
                # Check for company mentions
                for company_key, doc_id in company_to_doc.items():
                    if company_key in question_lower:
                        document_id = doc_id
                        break
                
                # Get expected answer - check multiple possible field names
                expected_answer = (
                    qa.get("expected_answer_text") or 
                    qa.get("expected_answer") or 
                    qa.get("answer") or
                    None
                )
                
                question = db_service.create_competency_question(
                    db=db,
                    question_text=question_text,
                    category_id=None,  # Categories not set up yet
                    document_id=document_id,  # Link to specific document if found
                    expected_answer_text=expected_answer,  # Can be None - tests will still run
                    confidence_threshold=0.7,
                    created_by="api_load"
                )
                loaded_count += 1
            except Exception as e:
                errors.append(f"Error loading question '{qa.get('id', 'unknown')}': {str(e)}")
        
        db.commit()
        
        return {
            "message": f"Loaded {loaded_count} questions from {qa_file}",
            "loaded_count": loaded_count,
            "total_in_file": len(qa_pairs),
            "errors": errors if errors else None,
            "cleared_existing": clear_existing
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {str(e)}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error loading questions from JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/questions/all")
async def delete_all_questions():
    """Delete all competency questions and related test data"""
    db = get_db_session()
    try:
        # Delete test feedback first (foreign key constraint)
        feedback_count = db.query(TestFeedback).count()
        db.query(TestFeedback).delete()
        
        # Delete test runs
        test_runs_count = db.query(TestRun).count()
        db.query(TestRun).delete()
        
        # Delete questions
        questions_count = db.query(CompetencyQuestion).count()
        db.query(CompetencyQuestion).delete()
        
        db.commit()
        
        return {
            "message": f"Deleted {questions_count} questions, {test_runs_count} test runs, {feedback_count} feedback records",
            "questions_deleted": questions_count,
            "test_runs_deleted": test_runs_count,
            "feedback_deleted": feedback_count
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting all questions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/questions/{question_id}")
async def delete_question(question_id: str):
    """Delete a competency question"""
    db = get_db_session()
    try:
        question = db.query(CompetencyQuestion).filter(CompetencyQuestion.id == question_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")

        # Delete associated test runs and feedback first
        db.query(TestFeedback).filter(TestFeedback.test_run_id.in_(
            db.query(TestRun.id).filter(TestRun.question_id == question_id)
        )).delete(synchronize_session=False)

        db.query(TestRun).filter(TestRun.question_id == question_id).delete()

        # Delete the question
        db.delete(question)
        db.commit()

        return {"message": "Question deleted successfully", "question_id": question_id}
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

        # Calculate accuracy using LLM-based evaluation
        accuracy_score = None
        llm_confidence = None
        llm_correctness = None
        evaluation_reasoning = None
        
        if question.expected_answer_text and answer_obj.text:
            # Use LLM-based evaluator for semantic comparison
            try:
                # Build context chunks from citations for better evaluation
                context_chunks = []
                if answer_obj.citations:
                    context_chunks = [
                        {
                            "text": c.excerpt or "",
                            "doc_id": c.doc_id,
                            "clause_number": c.clause_number,
                            "page_num": c.page_num
                        }
                        for c in answer_obj.citations
                    ]
                
                eval_result = await answer_evaluator.evaluate_answer(
                    question=question.question_text,
                    actual_answer=answer_obj.text,
                    expected_answer=question.expected_answer_text,
                    context_chunks=context_chunks
                )
                
                llm_confidence = eval_result.get("confidence", 0.0)
                llm_correctness = eval_result.get("correctness", False)
                evaluation_reasoning = eval_result.get("reasoning", "")
                
                # Use LLM confidence as accuracy score
                accuracy_score = llm_confidence
                
            except Exception as e:
                logger.error(f"Error evaluating answer with LLM: {e}")
                # Fallback to simple string matching if LLM evaluation fails
                expected = question.expected_answer_text.lower().strip()
                actual = answer_obj.text.lower().strip()

                if expected in actual or actual in expected:
                    accuracy_score = 0.9
                elif expected and actual:
                    expected_words = set(expected.split())
                    actual_words = set(actual.split())
                    if expected_words and actual_words:
                        overlap = len(expected_words & actual_words)
                        accuracy_score = overlap / max(len(expected_words), len(actual_words))
        elif answer_obj.text:
            # No expected answer, evaluate quality only
            try:
                context_chunks = []
                if answer_obj.citations:
                    context_chunks = [
                        {
                            "text": c.excerpt or "",
                            "doc_id": c.doc_id,
                            "clause_number": c.clause_number,
                            "page_num": c.page_num
                        }
                        for c in answer_obj.citations
                    ]
                
                eval_result = await answer_evaluator.evaluate_answer_quality(
                    question=question.question_text,
                    answer=answer_obj.text,
                    context_chunks=context_chunks
                )
                
                llm_confidence = eval_result.get("confidence", 0.0)
                llm_correctness = eval_result.get("correctness", False)
                evaluation_reasoning = eval_result.get("reasoning", "")
                accuracy_score = llm_confidence
                
            except Exception as e:
                logger.error(f"Error evaluating answer quality with LLM: {e}")
                # Fallback: basic heuristic
                if answer_obj.text and len(answer_obj.text) > 10 and "cannot find" not in answer_obj.text.lower():
                    accuracy_score = 0.6
                else:
                    accuracy_score = 0.2

        # Store test run with full citations and model configuration
        citations_data = [
            {
                "doc_id": c.doc_id,
                "clause_number": c.clause_number,
                "page_num": c.page_num,
                "span_start": c.span_start,
                "span_end": c.span_end,
                "source_uri": c.source_uri,
                "excerpt": c.excerpt
            }
            for c in answer_obj.citations
        ]

        # Store model configuration for debugging
        model_config = {
            "llm_provider": os.getenv("LLM_PROVIDER", "unknown"),
            "llm_model": os.getenv("OLLAMA_MODEL") or os.getenv("OPENAI_MODEL", "unknown"),
            "context_length": os.getenv("OLLAMA_CONTEXT_LENGTH", "unknown"),
            "evaluation_method": "llm_based" if llm_confidence is not None else "fallback",
            "llm_confidence": llm_confidence,
            "llm_correctness": llm_correctness,
            "evaluation_reasoning": evaluation_reasoning
        }

        test_run = TestRun(
            question_id=request.question_id,
            answer_text=answer_obj.text,
            retrieved_clauses=[c.doc_id for c in answer_obj.citations],  # Keep for backward compatibility
            citations_json=citations_data,  # Store full citations
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
            "accuracy_score": accuracy_score,
            "llm_confidence": llm_confidence,
            "llm_correctness": llm_correctness,
            "evaluation_reasoning": evaluation_reasoning,
            "model_config": model_config,
            "citations": [
                {
                    "doc_id": c.doc_id,
                    "clause_number": c.clause_number,
                    "page_num": c.page_num,
                    "span_start": c.span_start,
                    "span_end": c.span_end,
                    "source_uri": c.source_uri,
                    "excerpt": c.excerpt
                }
                for c in answer_obj.citations
            ],
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
                    "response_time_ms": tr.response_time_ms,
                    "retrieved_clauses": tr.retrieved_clauses
                }
                for tr in test_runs
            ],
            "total": total
        }
    finally:
        db.close()


@router.get("/test/results/latest")
async def get_latest_test_results():
    """Get the latest test result for each active question"""
    db = get_db_session()
    try:
        # Get all active questions
        questions = db.query(CompetencyQuestion).filter(
            CompetencyQuestion.is_active == True
        ).all()

        results = []
        for question in questions:
            # Get the most recent test run for this question
            latest_run = db.query(TestRun).filter(
                TestRun.question_id == question.id
            ).order_by(TestRun.run_at.desc()).first()

            if latest_run:
                # Calculate passed status using question's confidence threshold
                confidence_threshold = question.confidence_threshold if question.confidence_threshold is not None else 0.7
                passed = (
                    latest_run.accuracy_score is not None and
                    latest_run.accuracy_score >= confidence_threshold
                )

                # Build citations from stored citations_json (full citation data)
                citations = []
                if latest_run.citations_json:
                    # Use full citation data if available
                    citations = latest_run.citations_json
                elif latest_run.retrieved_clauses:
                    # Fallback to doc_ids only (backward compatibility)
                    citations = [
                        {"doc_id": doc_id, "clause_number": None, "page_num": None}
                        for doc_id in latest_run.retrieved_clauses
                    ]

                results.append({
                    "test_run_id": str(latest_run.id),
                    "question_id": str(question.id),
                    "question_text": question.question_text,
                    "expected_answer": question.expected_answer_text,
                    "document_id": str(question.document_id) if question.document_id else None,
                    "passed": passed,
                    "answer": latest_run.answer_text,
                    "actual_answer": latest_run.answer_text,
                    "accuracy_score": latest_run.accuracy_score,
                    "citations": citations,
                    "citations_count": len(latest_run.retrieved_clauses) if latest_run.retrieved_clauses else 0,
                    "response_time_ms": latest_run.response_time_ms,
                    "run_at": latest_run.run_at
                })

        # Calculate summary stats
        passed_count = sum(1 for r in results if r.get("passed"))
        failed_count = len(results) - passed_count
        pass_rate = (passed_count / len(results) * 100) if results else 0

        return {
            "total": len(results),
            "passed": passed_count,
            "failed": failed_count,
            "passRate": pass_rate,
            "results": results
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

        # Initialize progress tracking
        with _test_progress_lock:
            _test_progress["is_running"] = True
            _test_progress["total"] = len(questions)
            _test_progress["completed"] = 0
            _test_progress["current"] = None
            _test_progress["errors"] = 0
            _test_progress["passed"] = 0
            _test_progress["failed"] = 0

        results = []
        total_passed = 0
        total_failed = 0

        for idx, question in enumerate(questions, 1):
            # Update progress - currently processing this question
            with _test_progress_lock:
                _test_progress["current"] = question.question_text[:60] + "..." if len(question.question_text) > 60 else question.question_text
                _test_progress["completed"] = idx - 1
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

                # Calculate accuracy using LLM-based evaluation
                accuracy_score = None
                llm_confidence = None
                llm_correctness = None
                evaluation_reasoning = None
                
                if question.expected_answer_text and answer_obj.text:
                    # Use LLM-based evaluator for semantic comparison
                    try:
                        # Build context chunks from citations for better evaluation
                        context_chunks = []
                        if answer_obj.citations:
                            context_chunks = [
                                {
                                    "text": c.excerpt or "",
                                    "doc_id": c.doc_id,
                                    "clause_number": c.clause_number,
                                    "page_num": c.page_num
                                }
                                for c in answer_obj.citations
                            ]
                        
                        eval_result = await answer_evaluator.evaluate_answer(
                            question=question.question_text,
                            actual_answer=answer_obj.text,
                            expected_answer=question.expected_answer_text,
                            context_chunks=context_chunks
                        )
                        
                        llm_confidence = eval_result.get("confidence", 0.0)
                        llm_correctness = eval_result.get("correctness", False)
                        evaluation_reasoning = eval_result.get("reasoning", "")
                        
                        # Use LLM confidence as accuracy score
                        accuracy_score = llm_confidence
                        
                    except Exception as e:
                        logger.error(f"Error evaluating answer with LLM: {e}")
                        # Fallback to simple string matching if LLM evaluation fails
                        expected = question.expected_answer_text.lower().strip()
                        actual = answer_obj.text.lower().strip()

                        if expected in actual or actual in expected:
                            accuracy_score = 0.9
                        elif expected and actual:
                            expected_words = set(expected.split())
                            actual_words = set(actual.split())
                            if expected_words and actual_words:
                                overlap = len(expected_words & actual_words)
                                accuracy_score = overlap / max(len(expected_words), len(actual_words))
                elif answer_obj.text:
                    # No expected answer, evaluate quality only
                    try:
                        context_chunks = []
                        if answer_obj.citations:
                            context_chunks = [
                                {
                                    "text": c.excerpt or "",
                                    "doc_id": c.doc_id,
                                    "clause_number": c.clause_number,
                                    "page_num": c.page_num
                                }
                                for c in answer_obj.citations
                            ]
                        
                        eval_result = await answer_evaluator.evaluate_answer_quality(
                            question=question.question_text,
                            answer=answer_obj.text,
                            context_chunks=context_chunks
                        )
                        
                        llm_confidence = eval_result.get("confidence", 0.0)
                        llm_correctness = eval_result.get("correctness", False)
                        evaluation_reasoning = eval_result.get("reasoning", "")
                        accuracy_score = llm_confidence
                        
                    except Exception as e:
                        logger.error(f"Error evaluating answer quality with LLM: {e}")
                        # Fallback: basic heuristic
                        if answer_obj.text and len(answer_obj.text) > 10 and "cannot find" not in answer_obj.text.lower():
                            accuracy_score = 0.6
                        else:
                            accuracy_score = 0.2

                # Check if test passed (has answer, reasonable response time, and meets confidence threshold)
                # Use confidence threshold from the question, default to 0.7
                confidence_threshold = question.confidence_threshold if question.confidence_threshold is not None else 0.7
                passed = (
                    answer_obj.text and
                    len(answer_obj.text) > 10 and
                    response_time_ms < 30000 and
                    (accuracy_score is not None and accuracy_score >= confidence_threshold)
                )

                if passed:
                    total_passed += 1
                    with _test_progress_lock:
                        _test_progress["passed"] = total_passed
                else:
                    total_failed += 1
                    with _test_progress_lock:
                        _test_progress["failed"] = total_failed
                
                # Update progress - question completed
                with _test_progress_lock:
                    _test_progress["completed"] = idx

                # Store test run with full citations
                citations_data = [
                    {
                        "doc_id": c.doc_id,
                        "clause_number": c.clause_number,
                        "page_num": c.page_num,
                        "span_start": c.span_start,
                        "span_end": c.span_end,
                        "source_uri": c.source_uri,
                        "excerpt": c.excerpt
                    }
                    for c in answer_obj.citations
                ]

                test_run = TestRun(
                    question_id=str(question.id),
                    answer_text=answer_obj.text,
                    retrieved_clauses=[c.doc_id for c in answer_obj.citations],  # Keep for backward compatibility
                    citations_json=citations_data,  # Store full citations
                    accuracy_score=accuracy_score,
                    response_time_ms=response_time_ms
                )
                db.add(test_run)
                db.commit()
                db.refresh(test_run)

                # Build citations list from stored data
                citations = citations_data

                results.append({
                    "test_run_id": str(test_run.id),
                    "question_id": str(question.id),
                    "question_text": question.question_text,
                    "expected_answer": question.expected_answer_text,
                    "document_id": str(question.document_id) if question.document_id else None,
                    "passed": passed,
                    "answer": answer_obj.text,
                    "actual_answer": answer_obj.text,
                    "accuracy_score": accuracy_score,
                    "llm_confidence": llm_confidence,
                    "llm_correctness": llm_correctness,
                    "evaluation_reasoning": evaluation_reasoning,
                    "model_config": {
                        "llm_provider": os.getenv("LLM_PROVIDER", "unknown"),
                        "llm_model": os.getenv("OLLAMA_MODEL") or os.getenv("OPENAI_MODEL", "unknown"),
                        "context_length": os.getenv("OLLAMA_CONTEXT_LENGTH", "unknown")
                    },
                    "citations": citations,
                    "citations_count": len(answer_obj.citations),
                    "response_time_ms": response_time_ms,
                    "run_at": test_run.run_at
                })

            except Exception as e:
                logger.error(f"Error testing question {question.id} ({question.question_text[:50]}...): {e}", exc_info=True)
                total_failed += 1
                with _test_progress_lock:
                    _test_progress["failed"] = total_failed
                    _test_progress["errors"] += 1
                    _test_progress["completed"] = idx
                results.append({
                    "question_id": str(question.id),
                    "question_text": question.question_text,
                    "expected_answer": question.expected_answer_text,
                    "passed": False,
                    "error": str(e),
                    "accuracy_score": 0.0
                })

        # Reset progress tracking
        with _test_progress_lock:
            _test_progress["is_running"] = False
            _test_progress["current"] = None

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


@router.put("/threshold/global")
async def set_global_threshold(threshold: float = Query(..., ge=0.0, le=1.0)):
    """Set confidence threshold for all active questions"""
    db = get_db_session()
    try:
        # Update all active questions with the new threshold
        updated_count = db.query(CompetencyQuestion).filter(
            CompetencyQuestion.is_active == True
        ).update(
            {CompetencyQuestion.confidence_threshold: threshold},
            synchronize_session=False
        )
        db.commit()

        return {
            "message": f"Updated confidence threshold for {updated_count} questions",
            "threshold": threshold,
            "updated_count": updated_count
        }
    finally:
        db.close()


@router.get("/threshold/global")
async def get_global_threshold():
    """Get the current global confidence threshold (from first active question)"""
    db = get_db_session()
    try:
        # Get threshold from first active question as the "global" value
        question = db.query(CompetencyQuestion).filter(
            CompetencyQuestion.is_active == True
        ).first()

        if question:
            threshold = question.confidence_threshold if question.confidence_threshold is not None else 0.7
        else:
            threshold = 0.7

        return {
            "threshold": threshold
        }
    finally:
        db.close()
