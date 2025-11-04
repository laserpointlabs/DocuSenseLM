#!/usr/bin/env python3
"""
Generate sample competency questions with expected answers
This is a simplified version that can be run directly in the container
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import Document, DocumentMetadata, DocumentStatus, CompetencyQuestion, DocumentChunk, Party


def generate_sample_questions(limit=10):
    """Generate sample questions with expected answers"""
    db = get_db_session()
    all_questions = []

    try:
        docs = db.query(Document).filter(Document.status == DocumentStatus.PROCESSED).limit(3).all()

        for doc in docs:
            metadata = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == doc.id).first()
            if not metadata:
                continue

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
                term_str = f"{years} year{'s' if years > 1 else ''}" if years > 0 else f"{metadata.term_months} months"
                all_questions.append({
                    "question": f"What is the term (duration) of the {doc.filename} NDA?",
                    "expected_answer": term_str,
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
            valid_parties = [p.party_name for p in parties if len(p.party_name.strip()) > 3 and 'executed' not in p.party_name.lower()]
            if len(valid_parties) >= 2:
                all_questions.append({
                    "question": f"Who are the parties to the {doc.filename} NDA?",
                    "expected_answer": " and ".join(valid_parties[:2]),
                    "document_id": str(doc.id),
                    "verification_hint": f"Check the parties section in {doc.filename}"
                })

            if len(all_questions) >= limit:
                all_questions = all_questions[:limit]
                break

        return all_questions
    finally:
        db.close()


def create_questions(questions):
    """Create questions in database"""
    db = get_db_session()
    created = 0
    try:
        for q in questions:
            question = CompetencyQuestion(
                question_text=q["question"],
                document_id=q["document_id"],
                verification_hint=q.get("verification_hint"),
                expected_answer_text=q["expected_answer"],
                created_by="script"
            )
            db.add(question)
            created += 1
        db.commit()
        return created
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 70)
    print("Generating Sample Questions with Expected Answers")
    print("=" * 70)
    print()

    questions = generate_sample_questions(limit=10)

    print(f"Generated {len(questions)} questions:")
    for i, q in enumerate(questions, 1):
        print(f"\n{i}. {q['question']}")
        print(f"   Expected: {q['expected_answer']}")

    print("\n" + "=" * 70)
    print("Creating questions in database...")
    print("=" * 70)

    created = create_questions(questions)
    print(f"✅ Created {created} questions with expected answers")
