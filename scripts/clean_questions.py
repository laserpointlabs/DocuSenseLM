#!/usr/bin/env python3
"""
Script to delete all competency questions from the database
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import CompetencyQuestion, TestRun, TestFeedback

def delete_all_questions():
    """Delete all competency questions and related test runs/feedback"""
    db = get_db_session()
    try:
        # Delete test feedback first (foreign key constraint)
        feedback_count = db.query(TestFeedback).count()
        db.query(TestFeedback).delete()
        print(f"   - Deleted {feedback_count} test feedback records")
        
        # Delete test runs
        test_runs_count = db.query(TestRun).count()
        db.query(TestRun).delete()
        print(f"   - Deleted {test_runs_count} test run records")
        
        # Delete questions
        questions_count = db.query(CompetencyQuestion).count()
        db.query(CompetencyQuestion).delete()
        print(f"   - Deleted {questions_count} competency questions")
        
        db.commit()
        print(f"\n✅ Successfully deleted all competency questions and test data")
        print(f"   Total: {questions_count} questions, {test_runs_count} test runs, {feedback_count} feedback records")
    except Exception as e:
        db.rollback()
        print(f"❌ Error deleting questions: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 70)
    print("Clean Competency Questions")
    print("=" * 70)
    
    response = input("\n⚠️  This will delete ALL competency questions and test data. Continue? (yes/no): ")
    if response.lower() != "yes":
        print("Cancelled.")
        sys.exit(0)
    
    delete_all_questions()
    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)

