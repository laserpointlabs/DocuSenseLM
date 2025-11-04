#!/usr/bin/env python3
"""
Review and test competency questions
Shows questions with expected answers, runs tests, and displays results for approval
"""
import os
import sys
import asyncio
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import CompetencyQuestion, DocumentStatus
from api.services.answer_service import answer_service
from datetime import datetime


def get_active_questions() -> List[Dict]:
    """Get all active questions with expected answers"""
    db = get_db_session()
    try:
        questions = db.query(CompetencyQuestion).filter(
            CompetencyQuestion.is_active == True
        ).all()

        return [
            {
                "id": str(q.id),
                "question_text": q.question_text,
                "expected_answer": q.expected_answer_text,
                "document_id": str(q.document_id) if q.document_id else None,
                "verification_hint": q.verification_hint,
                "expected_clause": q.expected_clause,
                "expected_page": q.expected_page
            }
            for q in questions
        ]
    finally:
        db.close()


async def run_test_for_question(question: Dict) -> Dict:
    """Run a test for a single question and return results"""
    try:
        # Get document filter if question is document-specific
        filters = None
        if question.get("document_id"):
            filters = {"document_id": question["document_id"]}

        # Run answer generation
        start_time = datetime.now()
        answer_obj = await answer_service.generate_answer(
            question=question["question_text"],
            filters=filters
        )
        end_time = datetime.now()

        response_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Calculate confidence/accuracy
        expected = question.get("expected_answer", "").lower().strip()
        actual = answer_obj.text.lower().strip() if answer_obj.text else ""

        accuracy_score = None
        if expected and actual:
            if expected in actual or actual in expected:
                accuracy_score = 0.9
            else:
                expected_words = set(expected.split())
                actual_words = set(actual.split())
                if expected_words and actual_words:
                    overlap = len(expected_words & actual_words)
                    accuracy_score = overlap / max(len(expected_words), len(actual_words))

        return {
            "question_id": question["id"],
            "question_text": question["question_text"],
            "expected_answer": question["expected_answer"],
            "actual_answer": answer_obj.text,
            "accuracy_score": accuracy_score,
            "response_time_ms": response_time_ms,
            "citations_count": len(answer_obj.citations),
            "passed": accuracy_score is not None and accuracy_score >= 0.7
        }
    except Exception as e:
        return {
            "question_id": question["id"],
            "question_text": question["question_text"],
            "expected_answer": question["expected_answer"],
            "actual_answer": None,
            "error": str(e),
            "passed": False
        }


async def review_and_test_all():
    """Review all questions and run tests"""
    print("=" * 70)
    print("Competency Question Review and Test")
    print("=" * 70)
    print()

    # Get all questions
    questions = get_active_questions()

    if not questions:
        print("❌ No active questions found. Run generate_questions_with_answers.py first.")
        return

    print(f"📋 Found {len(questions)} questions to review")
    print()
    print("=" * 70)
    print("Running Tests...")
    print("=" * 70)
    print()

    # Run tests for all questions
    results = []
    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] Testing: {question['question_text'][:60]}...")
        result = await run_test_for_question(question)
        results.append(result)

        # Show quick result
        if result.get("error"):
            print(f"   ❌ Error: {result['error']}")
        elif result.get("passed"):
            print(f"   ✅ Passed (Confidence: {(result.get('accuracy_score', 0) * 100):.1f}%)")
        else:
            print(f"   ⚠️  Failed (Confidence: {(result.get('accuracy_score', 0) * 100):.1f}%)")
        print()

    # Display full results
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    print()

    passed = sum(1 for r in results if r.get("passed"))
    failed = len(results) - passed
    pass_rate = (passed / len(results) * 100) if results else 0

    print(f"Total Questions: {len(results)}")
    print(f"Passed: {passed} ({(passed/len(results)*100):.1f}%)")
    print(f"Failed: {failed} ({(failed/len(results)*100):.1f}%)")
    print()

    # Detailed results
    print("=" * 70)
    print("Detailed Results")
    print("=" * 70)
    print()

    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result.get("passed") else "❌ FAIL"
        confidence = result.get("accuracy_score")
        confidence_str = f"{(confidence * 100):.1f}%" if confidence else "N/A"

        print(f"[{i}] {status} - Confidence: {confidence_str}")
        print(f"    Question: {result['question_text']}")
        print(f"    Expected: {result.get('expected_answer', 'N/A')}")
        print(f"    Actual:   {result.get('actual_answer', 'No answer generated')[:100]}...")
        if result.get("error"):
            print(f"    Error:    {result['error']}")
        print(f"    Response Time: {result.get('response_time_ms', 'N/A')}ms")
        print(f"    Citations: {result.get('citations_count', 0)}")
        print()

    # Approval summary
    print("=" * 70)
    print("Review Summary")
    print("=" * 70)
    print()
    print(f"✅ {passed} questions passed (confidence >= 70%)")
    print(f"❌ {failed} questions failed (confidence < 70% or error)")
    print(f"📊 Pass Rate: {pass_rate:.1f}%")
    print()

    if pass_rate >= 70:
        print("✅ Overall system performance: GOOD")
    elif pass_rate >= 50:
        print("⚠️  Overall system performance: NEEDS IMPROVEMENT")
    else:
        print("❌ Overall system performance: POOR")

    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(review_and_test_all())
