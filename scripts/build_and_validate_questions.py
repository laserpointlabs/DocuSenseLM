#!/usr/bin/env python3
"""
Build competency questions with answers and validate them
This script:
1. Generates questions with expected answers from documents
2. Creates them in the database
3. Runs validation tests
4. Shows results for review
"""
import sys
import os
import asyncio
from typing import List, Dict, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import (
    Document, DocumentMetadata, DocumentStatus, CompetencyQuestion, 
    DocumentChunk, Party, TestRun
)
from api.services.answer_service import answer_service


def generate_questions_from_documents(limit=10) -> List[Dict]:
    """Generate questions with expected answers from processed documents"""
    db = get_db_session()
    all_questions = []
    
    try:
        docs = db.query(Document).filter(Document.status == DocumentStatus.PROCESSED).limit(3).all()
        
        print(f"📄 Found {len(docs)} processed documents")
        
        for doc in docs:
            metadata = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == doc.id).first()
            if not metadata:
                print(f"   ⚠️  Skipping {doc.filename} - no metadata")
                continue
            
            print(f"   📋 Processing: {doc.filename}")
            
            # Question 1: Effective Date
            if metadata.effective_date:
                effective_date_str = metadata.effective_date.strftime("%B %d, %Y")
                all_questions.append({
                    "question": f"What is the effective date of the {doc.filename} NDA?",
                    "expected_answer": effective_date_str,
                    "document_id": str(doc.id),
                    "verification_hint": f"Check the effective date clause in {doc.filename}"
                })
            
            # Question 2: Term
            if metadata.term_months:
                years = metadata.term_months // 12
                months = metadata.term_months % 12
                if years > 0 and months == 0:
                    term_str = f"{years} year{'s' if years > 1 else ''}"
                elif years > 0 and months > 0:
                    term_str = f"{years} year{'s' if years > 1 else ''} and {months} month{'s' if months > 1 else ''}"
                else:
                    term_str = f"{months} month{'s' if months > 1 else ''}"
                
                all_questions.append({
                    "question": f"What is the term (duration) of the {doc.filename} NDA?",
                    "expected_answer": term_str,
                    "document_id": str(doc.id),
                    "verification_hint": f"Check the term clause in {doc.filename}"
                })
                
                # Also add months version
                all_questions.append({
                    "question": f"What is the term of the {doc.filename} NDA in months?",
                    "expected_answer": str(metadata.term_months),
                    "document_id": str(doc.id),
                    "verification_hint": f"Check the term clause in {doc.filename}"
                })
            
            # Question 3: Governing Law
            if metadata.governing_law:
                all_questions.append({
                    "question": f"What is the governing law for the {doc.filename} NDA?",
                    "expected_answer": metadata.governing_law,
                    "document_id": str(doc.id),
                    "verification_hint": f"Check the governing law clause in {doc.filename}"
                })
            
            # Question 4: Mutual/Unilateral
            if metadata.is_mutual is not None:
                mutual_text = "mutual" if metadata.is_mutual else "unilateral"
                all_questions.append({
                    "question": f"Is the {doc.filename} NDA a mutual or unilateral agreement?",
                    "expected_answer": mutual_text,
                    "document_id": str(doc.id),
                    "verification_hint": f"Check if both parties have obligations in {doc.filename}"
                })
            
            # Question 5: Parties
            parties = db.query(Party).filter(Party.document_id == doc.id).all()
            valid_parties = [p.party_name for p in parties 
                           if len(p.party_name.strip()) > 3 
                           and 'executed' not in p.party_name.lower()
                           and 'delivered' not in p.party_name.lower()]
            if len(valid_parties) >= 2:
                all_questions.append({
                    "question": f"Who are the parties to the {doc.filename} NDA?",
                    "expected_answer": " and ".join(valid_parties[:2]),
                    "document_id": str(doc.id),
                    "verification_hint": f"Check the parties section in {doc.filename}"
                })
            
            # Question 6: Survival Period
            if metadata.survival_months:
                years = metadata.survival_months // 12
                months = metadata.survival_months % 12
                if years > 0 and months == 0:
                    survival_str = f"{years} year{'s' if years > 1 else ''}"
                elif years > 0 and months > 0:
                    survival_str = f"{years} year{'s' if years > 1 else ''} and {months} month{'s' if months > 1 else ''}"
                else:
                    survival_str = f"{months} month{'s' if months > 1 else ''}"
                
                all_questions.append({
                    "question": f"What is the survival period after expiration for the {doc.filename} NDA?",
                    "expected_answer": survival_str,
                    "document_id": str(doc.id),
                    "verification_hint": f"Check the survival clause in {doc.filename}"
                })
            
            # Limit total questions
            if len(all_questions) >= limit:
                all_questions = all_questions[:limit]
                break
        
        return all_questions
    finally:
        db.close()


def create_questions(questions: List[Dict]) -> List[str]:
    """Create questions in database and return question IDs"""
    db = get_db_session()
    question_ids = []
    created = 0
    
    try:
        for q in questions:
            question = CompetencyQuestion(
                question_text=q["question"],
                document_id=q["document_id"],
                verification_hint=q.get("verification_hint"),
                expected_answer_text=q["expected_answer"],
                created_by="build_and_validate_script"
            )
            db.add(question)
            db.flush()  # Get the ID
            question_ids.append(str(question.id))
            created += 1
        db.commit()
        print(f"✅ Created {created} questions in database")
        return question_ids
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating questions: {e}")
        return []
    finally:
        db.close()


async def validate_question(question: Dict, question_id: str) -> Dict:
    """Validate a single question by running it through the answer service"""
    try:
        # Get document filter if question is document-specific
        filters = None
        if question.get("document_id"):
            filters = {"document_id": question["document_id"]}
        
        # Run answer generation
        start_time = datetime.now()
        answer_obj = await answer_service.generate_answer(
            question=question["question"],
            filters=filters
        )
        end_time = datetime.now()
        
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Calculate accuracy/confidence
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
        
        # Determine pass/fail (70% threshold)
        passed = accuracy_score is not None and accuracy_score >= 0.7
        
        return {
            "question_id": question_id,
            "question_text": question["question"],
            "expected_answer": question["expected_answer"],
            "actual_answer": answer_obj.text,
            "accuracy_score": accuracy_score,
            "response_time_ms": response_time_ms,
            "citations_count": len(answer_obj.citations),
            "passed": passed,
            "error": None
        }
    except Exception as e:
        return {
            "question_id": question_id,
            "question_text": question["question"],
            "expected_answer": question.get("expected_answer", ""),
            "actual_answer": None,
            "accuracy_score": None,
            "response_time_ms": None,
            "citations_count": 0,
            "passed": False,
            "error": str(e)
        }


async def validate_all_questions(questions: List[Dict], question_ids: List[str]) -> List[Dict]:
    """Validate all questions and return results"""
    print("\n" + "=" * 70)
    print("Validating Questions...")
    print("=" * 70)
    print()
    
    results = []
    for i, (question, question_id) in enumerate(zip(questions, question_ids), 1):
        print(f"[{i}/{len(questions)}] Testing: {question['question'][:60]}...")
        result = await validate_question(question, question_id)
        results.append(result)
        
        if result.get("error"):
            print(f"   ❌ Error: {result['error']}")
        elif result.get("passed"):
            score = result.get("accuracy_score", 0) * 100
            print(f"   ✅ Passed (Confidence: {score:.1f}%)")
        else:
            score = result.get("accuracy_score", 0) * 100 if result.get("accuracy_score") else 0
            print(f"   ⚠️  Failed (Confidence: {score:.1f}%)")
    
    return results


def save_test_runs(results: List[Dict]):
    """Save test run results to database"""
    db = get_db_session()
    saved = 0
    
    try:
        for result in results:
            question_id = result["question_id"]
            question = db.query(CompetencyQuestion).filter(CompetencyQuestion.id == question_id).first()
            if not question:
                continue
            
            test_run = TestRun(
                question_id=question_id,
                accuracy_score=result.get("accuracy_score"),
                response_time_ms=result.get("response_time_ms"),
                answer_text=result.get("actual_answer"),
                citations_count=result.get("citations_count", 0)
            )
            # TestRun doesn't have a 'passed' field - we infer it from accuracy_score
            db.add(test_run)
            saved += 1
        
        db.commit()
        print(f"\n✅ Saved {saved} test run results to database")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error saving test runs: {e}")
    finally:
        db.close()


def display_results(results: List[Dict]):
    """Display validation results"""
    print("\n" + "=" * 70)
    print("Validation Results Summary")
    print("=" * 70)
    print()
    
    passed = sum(1 for r in results if r.get("passed"))
    failed = len(results) - passed
    pass_rate = (passed / len(results) * 100) if results else 0
    
    print(f"Total Questions: {len(results)}")
    print(f"✅ Passed: {passed} ({(passed/len(results)*100):.1f}%)")
    print(f"❌ Failed: {failed} ({(failed/len(results)*100):.1f}%)")
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
        print(f"    Expected: {result['expected_answer']}")
        actual = result.get('actual_answer', 'No answer generated')
        if len(actual) > 100:
            actual = actual[:100] + "..."
        print(f"    Actual:   {actual}")
        if result.get("error"):
            print(f"    Error:    {result['error']}")
        print(f"    Response Time: {result.get('response_time_ms', 'N/A')}ms")
        print(f"    Citations: {result.get('citations_count', 0)}")
        print()
    
    # Overall assessment
    print("=" * 70)
    print("Overall Assessment")
    print("=" * 70)
    print()
    
    if pass_rate >= 70:
        print("✅ Overall system performance: GOOD")
        print("   Questions are ready for use.")
    elif pass_rate >= 50:
        print("⚠️  Overall system performance: NEEDS IMPROVEMENT")
        print("   Review failed questions and consider adjusting expected answers.")
    else:
        print("❌ Overall system performance: POOR")
        print("   Significant issues detected. Review extraction and LLM configuration.")
    
    print()


async def main():
    """Main function"""
    print("=" * 70)
    print("Build and Validate Competency Questions")
    print("=" * 70)
    print()
    
    # Step 1: Generate questions
    print("Step 1: Generating questions with expected answers...")
    print("-" * 70)
    questions = generate_questions_from_documents(limit=10)
    
    if not questions:
        print("❌ No questions generated. Check document processing status.")
        return
    
    print(f"✅ Generated {len(questions)} questions")
    print()
    
    # Display questions
    print("Generated Questions:")
    for i, q in enumerate(questions, 1):
        print(f"  {i}. {q['question']}")
        print(f"     Expected: {q['expected_answer']}")
    print()
    
    # Step 2: Create questions in database
    print("Step 2: Creating questions in database...")
    print("-" * 70)
    question_ids = create_questions(questions)
    
    if not question_ids:
        print("❌ Failed to create questions. Aborting validation.")
        return
    
    # Step 3: Validate questions
    print("\nStep 3: Validating questions...")
    print("-" * 70)
    results = await validate_all_questions(questions, question_ids)
    
    # Step 4: Save test runs
    print("\nStep 4: Saving test results...")
    print("-" * 70)
    save_test_runs(results)
    
    # Step 5: Display results
    display_results(results)
    
    print("=" * 70)
    print("Done!")
    print("=" * 70)
    print()
    print("💡 Next Steps:")
    print("   - Review results above")
    print("   - Check UI at http://localhost:3000/competency")
    print("   - Approve questions that passed validation")


if __name__ == "__main__":
    asyncio.run(main())

