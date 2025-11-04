#!/usr/bin/env python3
"""
Generate competency questions with expected answers based on document content
This script extracts answers from documents and creates questions with expected answers
"""
import os
import sys
import argparse
from typing import List, Dict, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import Document, DocumentMetadata, DocumentStatus, CompetencyQuestion, DocumentChunk
from ingest.clause_extractor import clause_extractor
from ingest.parser import DocumentParser
from api.services.storage_service import storage_service
import tempfile


def get_processed_documents() -> List[Dict]:
    """Get list of processed documents"""
    db = get_db_session()
    try:
        docs = db.query(Document).filter(Document.status == DocumentStatus.PROCESSED).all()
        documents = []
        for doc in docs:
            metadata = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == doc.id).first()
            documents.append({
                "id": str(doc.id),
                "filename": doc.filename,
                "metadata": {
                    "effective_date": metadata.effective_date if metadata else None,
                    "governing_law": metadata.governing_law if metadata else None,
                    "is_mutual": metadata.is_mutual if metadata else None,
                    "term_months": metadata.term_months if metadata else None,
                    "survival_months": metadata.survival_months if metadata else None,
                }
            })
        return documents
    finally:
        db.close()


def generate_questions_with_answers(document_id: str, filename: str) -> List[Dict]:
    """Generate questions with expected answers for a document"""
    db = get_db_session()
    questions = []
    
    try:
        # Get document metadata
        metadata = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
        
        if not metadata:
            print(f"⚠️  No metadata found for {filename}")
            return questions
        
        # Question 1: Effective Date
        if metadata.effective_date:
            effective_date_str = metadata.effective_date.strftime("%B %d, %Y")
            questions.append({
                "question": f"What is the effective date of the {filename} NDA?",
                "expected_answer": effective_date_str,
                "document_id": document_id,
                "verification_hint": f"Check the effective date clause in {filename}"
            })
        
        # Question 2: Term/Duration
        if metadata.term_months:
            years = metadata.term_months // 12
            months = metadata.term_months % 12
            if years > 0 and months == 0:
                term_str = f"{years} year{'s' if years > 1 else ''}"
            elif years > 0 and months > 0:
                term_str = f"{years} year{'s' if years > 1 else ''} and {months} month{'s' if months > 1 else ''}"
            else:
                term_str = f"{months} month{'s' if months > 1 else ''}"
            
            questions.append({
                "question": f"What is the term (duration) of the {filename} NDA?",
                "expected_answer": term_str,
                "document_id": document_id,
                "verification_hint": f"Check the term clause in {filename}"
            })
            
            # Also add months version
            questions.append({
                "question": f"What is the term of the {filename} NDA in months?",
                "expected_answer": str(metadata.term_months),
                "document_id": document_id,
                "verification_hint": f"Check the term clause in {filename}"
            })
        
        # Question 3: Governing Law
        if metadata.governing_law:
            questions.append({
                "question": f"What is the governing law for the {filename} NDA?",
                "expected_answer": metadata.governing_law,
                "document_id": document_id,
                "verification_hint": f"Check the governing law clause in {filename}"
            })
        
        # Question 4: Mutual/Unilateral
        if metadata.is_mutual is not None:
            mutual_text = "mutual" if metadata.is_mutual else "unilateral"
            questions.append({
                "question": f"Is the {filename} NDA a mutual or unilateral agreement?",
                "expected_answer": mutual_text,
                "document_id": document_id,
                "verification_hint": f"Check if both parties have obligations in {filename}"
            })
        
        # Question 5: Parties
        from api.db.schema import Party
        parties = db.query(Party).filter(Party.document_id == document_id).all()
        if parties:
            party_names = [p.party_name for p in parties if len(p.party_name.strip()) > 3]
            if len(party_names) >= 2:
                # Filter out invalid party names
                valid_parties = [p for p in party_names if not any(word in p.lower() for word in ['executed', 'delivered', 'supersedes', 'the parties'])]
                if len(valid_parties) >= 2:
                    questions.append({
                        "question": f"Who are the parties to the {filename} NDA?",
                        "expected_answer": " and ".join(valid_parties[:2]),  # Limit to 2 parties
                        "document_id": document_id,
                        "verification_hint": f"Check the parties section in {filename}"
                    })
        
        # Question 6: Survival Period (if available)
        if metadata.survival_months:
            years = metadata.survival_months // 12
            months = metadata.survival_months % 12
            if years > 0 and months == 0:
                survival_str = f"{years} year{'s' if years > 1 else ''}"
            elif years > 0 and months > 0:
                survival_str = f"{years} year{'s' if years > 1 else ''} and {months} month{'s' if months > 1 else ''}"
            else:
                survival_str = f"{months} month{'s' if months > 1 else ''}"
            
            questions.append({
                "question": f"What is the survival period after expiration for the {filename} NDA?",
                "expected_answer": survival_str,
                "document_id": document_id,
                "verification_hint": f"Check the survival clause in {filename}"
            })
        
        # Question 7-10: Key Clauses (limit to 3-4 key clauses)
        key_clauses = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id,
            DocumentChunk.clause_title.isnot(None),
            DocumentChunk.section_type == 'clause'
        ).limit(4).all()
        
        for clause in key_clauses:
            clause_title = clause.clause_title
            if clause_title and len(clause_title) > 5:  # Skip very short titles
                # For clause questions, we'll use a generic expected answer format
                # The actual answer should reference the clause content
                questions.append({
                    "question": f"What does the {clause_title} clause specify in the {filename} NDA?",
                    "expected_answer": f"The {clause_title} clause specifies the terms and conditions related to {clause_title.lower()}.",
                    "document_id": document_id,
                    "verification_hint": f"Check clause {clause.clause_number or 'N/A'} ({clause_title}) on page {clause.page_num} in {filename}",
                    "expected_clause": clause_title,
                    "expected_page": clause.page_num
                })
        
    finally:
        db.close()
    
    return questions


def create_question_with_answer(question_text: str, expected_answer: str, document_id: str, 
                                verification_hint: str = None, expected_clause: str = None, 
                                expected_page: int = None) -> str:
    """Create a competency question with expected answer"""
    db = get_db_session()
    try:
        question = CompetencyQuestion(
            question_text=question_text,
            category_id=None,
            document_id=document_id,
            verification_hint=verification_hint,
            expected_clause=expected_clause,
            expected_page=expected_page,
            expected_answer_text=expected_answer,
            created_by="script"
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        return str(question.id)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Generate competency questions with expected answers from documents")
    parser.add_argument("--create", action="store_true", help="Actually create questions in database")
    parser.add_argument("--document-id", type=str, help="Generate for specific document ID")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of questions to create (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run - don't create questions")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Competency Question Generator with Expected Answers")
    print("=" * 70)
    print()
    
    # Get documents
    if args.document_id:
        documents = [{"id": args.document_id}]
        print(f"📄 Generating questions for specific document: {args.document_id}")
    else:
        documents = get_processed_documents()
        print(f"📄 Found {len(documents)} processed documents")
    
    all_questions = []
    
    for doc_info in documents:
        document_id = doc_info["id"]
        filename = doc_info.get("filename", "Unknown")
        
        print(f"\n📋 Analyzing: {filename}")
        
        questions = generate_questions_with_answers(document_id, filename)
        print(f"   ✅ Generated {len(questions)} questions with expected answers")
        
        for q in questions:
            q["document_filename"] = filename
            all_questions.append(q)
        
        # Limit total questions
        if len(all_questions) >= args.limit:
            all_questions = all_questions[:args.limit]
            print(f"\n⚠️  Limited to {args.limit} questions total")
            break
    
    # Display questions
    print("\n" + "=" * 70)
    print(f"Generated {len(all_questions)} questions with expected answers")
    print("=" * 70)
    
    for i, q in enumerate(all_questions, 1):
        print(f"\n[{i}] Question: {q['question']}")
        print(f"    Expected Answer: {q['expected_answer']}")
        print(f"    Document: {q.get('document_filename', 'Unknown')}")
        print(f"    Verification: {q.get('verification_hint', 'Review document')}")
        if q.get('expected_clause'):
            print(f"    Expected Clause: {q['expected_clause']} (Page {q.get('expected_page', '?')})")
    
    # Create questions in database
    if args.create and not args.dry_run:
        print("\n" + "=" * 70)
        print("Creating questions in database...")
        print("=" * 70)
        
        created_count = 0
        for q in all_questions:
            try:
                question_id = create_question_with_answer(
                    question_text=q['question'],
                    expected_answer=q['expected_answer'],
                    document_id=q['document_id'],
                    verification_hint=q.get('verification_hint'),
                    expected_clause=q.get('expected_clause'),
                    expected_page=q.get('expected_page')
                )
                created_count += 1
                print(f"✅ Created: {q['question'][:60]}...")
                print(f"   Expected: {q['expected_answer'][:60]}...")
            except Exception as e:
                print(f"❌ Failed to create question: {e}")
        
        print(f"\n✅ Created {created_count} questions with expected answers")
    elif args.dry_run:
        print("\n🔍 DRY RUN - No questions created. Use --create to create them.")
    else:
        print("\n💡 Use --create to create these questions in the database")
    
    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()

