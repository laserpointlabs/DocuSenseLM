#!/usr/bin/env python3
"""
Script to load competency questions from eval/qa_pairs.json into the database
and optionally run tests to verify they work with the currently loaded documents.
"""
import os
import sys
import json
import requests
import time
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from api.db import get_db_session
    from api.db.schema import CompetencyQuestion, Document, DocumentStatus
    from api.services.db_service import db_service
except ImportError:
    # If running outside container, add the project root to path
    import sys
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    from api.db import get_db_session
    from api.db.schema import CompetencyQuestion, Document, DocumentStatus
    from api.services.db_service import db_service

API_URL = os.getenv("API_URL", "http://localhost:8000")


def print_progress_bar(current: int, total: int, current_item: str = "", bar_length: int = 40, status: str = ""):
    """
    Print a progress bar similar to reindexing progress.
    
    Args:
        current: Current progress (0-indexed or 1-indexed)
        total: Total items
        current_item: Name of current item being processed
        bar_length: Length of progress bar in characters
        status: Optional status text (e.g., "PASSED", "FAILED")
    """
    # Ensure current is within bounds
    current = max(0, min(current, total))
    
    # Calculate percentage
    percent = (current / total * 100) if total > 0 else 0
    
    # Calculate filled length
    filled_length = int(bar_length * current // total) if total > 0 else 0
    
    # Create bar
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    # Build status prefix
    status_prefix = f"{status} - " if status else ""
    
    # Print progress bar
    if current_item:
        item_display = current_item[:55] + "..." if len(current_item) > 55 else current_item
        print(f"\r🧪 [{bar}] {current}/{total} ({percent:.1f}%) | {status_prefix}{item_display}", end='', flush=True)
    else:
        print(f"\r🧪 [{bar}] {current}/{total} ({percent:.1f}%)", end='', flush=True)


def load_qa_pairs() -> List[Dict]:
    """Load QA pairs from eval/qa_pairs.json"""
    qa_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "eval", "qa_pairs.json")
    if not os.path.exists(qa_file):
        raise FileNotFoundError(f"QA pairs file not found: {qa_file}")

    with open(qa_file, 'r') as f:
        return json.load(f)


def create_question_via_api(question_text: str, category: Optional[str] = None) -> Dict:
    """Create a competency question via API"""
    response = requests.post(
        f"{API_URL}/competency/questions",
        json={"question_text": question_text, "category_id": category}
    )
    response.raise_for_status()
    return response.json()


def create_question_via_db(question_text: str, category: Optional[str] = None) -> str:
    """Create a competency question directly in database"""
    db = get_db_session()
    try:
        question = db_service.create_competency_question(
            db=db,
            question_text=question_text,
            category_id=category,
            created_by="script"
        )
        return str(question.id)
    finally:
        db.close()


def get_loaded_documents() -> List[Dict]:
    """Get list of currently loaded and processed documents"""
    db = get_db_session()
    try:
        docs = db.query(Document).filter(Document.status == DocumentStatus.PROCESSED).all()
        return [
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "status": doc.status.value if hasattr(doc.status, 'value') else str(doc.status)
            }
            for doc in docs
        ]
    finally:
        db.close()


def run_test(question_id: str, document_id: Optional[str] = None) -> Dict:
    """Run a test for a competency question"""
    payload = {"question_id": question_id}
    if document_id:
        payload["document_id"] = document_id

    # Set timeout to 150 seconds (2.5 minutes) for conversational questions
    response = requests.post(
        f"{API_URL}/competency/test/run",
        json=payload,
        timeout=150.0
    )
    response.raise_for_status()
    return response.json()


def clean_all_questions():
    """Delete all competency questions and related test runs/feedback"""
    db = get_db_session()
    try:
        from api.db.schema import TestRun, TestFeedback
        
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
        print(f"🧹 Cleaned {questions_count} questions, {test_runs_count} test runs, {feedback_count} feedback records")
        return questions_count
    except Exception as e:
        db.rollback()
        print(f"❌ Error cleaning questions: {e}")
        raise
    finally:
        db.close()


def load_questions(use_api: bool = True, dry_run: bool = False) -> List[str]:
    """Load questions from QA pairs into the database"""
    qa_pairs = load_qa_pairs()
    question_ids = []

    print(f"📚 Found {len(qa_pairs)} QA pairs to load")

    if dry_run:
        print("🔍 DRY RUN MODE - No questions will be created")

    for i, qa in enumerate(qa_pairs, 1):
        question_text = qa.get("question", qa.get("question_text", ""))
        # category_id must be a UUID, not a string - for now, set to None
        # TODO: Create categories first or lookup category UUIDs
        category = None  # qa.get("category", None)  # Disabled until categories are set up

        if not question_text:
            print(f"⚠️  Skipping QA pair {i}: No question text")
            continue

        print(f"\n[{i}/{len(qa_pairs)}] Creating question: {question_text[:60]}...")

        if not dry_run:
            try:
                if use_api:
                    result = create_question_via_api(question_text, category)
                    question_id = result["id"]
                else:
                    question_id = create_question_via_db(question_text, category)

                question_ids.append(question_id)
                print(f"   ✅ Created question ID: {question_id}")
            except Exception as e:
                print(f"   ❌ Failed to create question: {e}")
        else:
            print(f"   [DRY RUN] Would create: {question_text[:60]}...")
            question_ids.append(f"dry-run-{i}")

    return question_ids


def run_tests_for_questions(question_ids: List[str], document_id: Optional[str] = None) -> Dict:
    """Run tests for all loaded questions"""
    # Filter out dry-run questions
    real_question_ids = [qid for qid in question_ids if not qid.startswith("dry-run-")]
    total = len(real_question_ids)
    
    print(f"\n🧪 Running tests for {total} questions...")
    print("=" * 70)

    results = {
        "total": total,
        "passed": 0,
        "failed": 0,
        "errors": [],
        "test_results": []
    }

    for i, question_id in enumerate(real_question_ids, 1):
        try:
            # Get question text for display
            db = get_db_session()
            try:
                question = db.query(CompetencyQuestion).filter(
                    CompetencyQuestion.id == question_id
                ).first()
                question_text = question.question_text if question else "Unknown"
            finally:
                db.close()

            # Update progress bar before test
            print_progress_bar(i - 1, total, question_text, status="Testing...")
            
            # Run test
            test_result = run_test(question_id, document_id)

            # Check if test passed (has answer and response time < 120s for conversational questions)
            # Conversational questions may take longer due to LLM processing
            response_time_ms = test_result.get("response_time_ms", 999999)
            passed = (
                test_result.get("answer") and
                len(test_result.get("answer", "")) > 10 and
                response_time_ms < 120000  # 2 minutes for conversational questions
            )

            # Update progress bar with result
            status_text = "✅ PASSED" if passed else "❌ FAILED"
            print_progress_bar(i, total, question_text, status=status_text)
            print()  # New line for next progress update

            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

            results["test_results"].append({
                "question_id": question_id,
                "question_text": question_text,
                "passed": passed,
                "response_time_ms": test_result.get("response_time_ms"),
                "answer_length": len(test_result.get("answer", ""))
            })

            # Small delay to avoid overwhelming the API
            time.sleep(0.5)

        except Exception as e:
            results["failed"] += 1
            error_msg = f"Error testing question {question_id}: {e}"
            results["errors"].append(error_msg)
            print(f"\r❌ ERROR testing question {i}/{total}: {e}")
            print()  # New line

    # Final progress bar update
    print_progress_bar(total, total, "")
    print()  # Final newline
    
    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Load competency questions and run tests")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually create questions")
    parser.add_argument("--use-api", action="store_true", default=True, help="Use API instead of direct DB access")
    parser.add_argument("--use-db", action="store_true", help="Use direct DB access instead of API")
    parser.add_argument("--test", action="store_true", help="Run tests after loading questions")
    parser.add_argument("--document-id", type=str, help="Test against specific document ID")
    parser.add_argument("--test-only", action="store_true", help="Only run tests, don't load questions")
    parser.add_argument("--clean", action="store_true", help="Clear all existing questions before loading new ones")

    args = parser.parse_args()

    use_api = args.use_api and not args.use_db

    print("=" * 70)
    print("Competency Question Loader")
    print("=" * 70)

    # Check loaded documents
    documents = get_loaded_documents()
    print(f"\n📄 Found {len(documents)} processed documents:")
    for doc in documents[:5]:  # Show first 5
        print(f"   - {doc['filename']}")
    if len(documents) > 5:
        print(f"   ... and {len(documents) - 5} more")

    if len(documents) == 0:
        print("\n⚠️  WARNING: No processed documents found. Tests may fail.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return

    question_ids = []

    if not args.test_only:
        # Clean existing questions if requested
        if args.clean:
            print("\n🧹 Cleaning existing questions...")
            if not args.dry_run:
                clean_all_questions()
            else:
                print("   [DRY RUN] Would clean all existing questions")
        
        # Load questions
        question_ids = load_questions(use_api=use_api, dry_run=args.dry_run)
        print(f"\n✅ Loaded {len(question_ids)} questions")
    else:
        # Get existing questions
        db = get_db_session()
        try:
            questions = db.query(CompetencyQuestion).filter(
                CompetencyQuestion.is_active == True
            ).all()
            question_ids = [str(q.id) for q in questions]
            print(f"\n📋 Found {len(question_ids)} existing questions to test")
        finally:
            db.close()

    if args.test and question_ids:
        # Run tests
        test_results = run_tests_for_questions(
            question_ids,
            document_id=args.document_id
        )

        # Print summary
        print("\n" + "=" * 70)
        print("Test Summary")
        print("=" * 70)
        print(f"Total questions tested: {test_results['total']}")
        print(f"✅ Passed: {test_results['passed']}")
        print(f"❌ Failed: {test_results['failed']}")

        if test_results['errors']:
            print(f"\n⚠️  Errors:")
            for error in test_results['errors']:
                print(f"   - {error}")

        # Calculate pass rate
        if test_results['total'] > 0:
            pass_rate = (test_results['passed'] / test_results['total']) * 100
            print(f"\n📊 Pass Rate: {pass_rate:.1f}%")

            if pass_rate >= 80:
                print("✅ Excellent! System is working well.")
            elif pass_rate >= 60:
                print("⚠️  System is working but could be improved.")
            else:
                print("❌ System needs attention. Many tests are failing.")

    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()
