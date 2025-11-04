#!/usr/bin/env python3
"""
Generate document-specific competency questions by analyzing loaded documents
and creating questions that can be verified by viewing the source document.
"""
import os
import sys
import json
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import Document, DocumentChunk, DocumentMetadata, DocumentStatus, CompetencyQuestion
from api.services.db_service import db_service
from llm.llm_factory import get_llm_client

def get_processed_documents() -> List[Dict]:
    """Get all processed documents with their metadata"""
    db = get_db_session()
    try:
        docs = db.query(Document).filter(Document.status == DocumentStatus.PROCESSED).all()
        result = []
        for doc in docs:
            # Get metadata
            metadata = db.query(DocumentMetadata).filter(
                DocumentMetadata.document_id == doc.id
            ).first()

            # Get a sample of chunks to understand document content
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id
            ).limit(5).all()

            result.append({
                "id": str(doc.id),
                "filename": doc.filename,
                "metadata": {
                    "effective_date": metadata.effective_date if metadata else None,
                    "governing_law": metadata.governing_law if metadata else None,
                    "is_mutual": metadata.is_mutual if metadata else None,
                    "term_months": metadata.term_months if metadata else None,
                    "survival_months": metadata.survival_months if metadata else None,
                },
                "sample_clauses": [chunk.clause_title or chunk.clause_number for chunk in chunks if chunk.clause_title or chunk.clause_number]
            })
        return result
    finally:
        db.close()


def extract_key_info_from_document(document_id: str) -> Dict:
    """Extract key information from a document to generate questions"""
    db = get_db_session()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return {}

        metadata = db.query(DocumentMetadata).filter(
            DocumentMetadata.document_id == document_id
        ).first()

        # Get key clauses
        chunks = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).filter(
            DocumentChunk.clause_title.isnot(None)
        ).limit(20).all()

        key_info = {
            "filename": doc.filename,
            "parties": [],
            "effective_date": metadata.effective_date if metadata else None,
            "governing_law": metadata.governing_law if metadata else None,
            "is_mutual": metadata.is_mutual if metadata else None,
            "term_months": metadata.term_months if metadata else None,
            "survival_months": metadata.survival_months if metadata else None,
            "key_clauses": []
        }

        # Get parties
        from api.db.schema import Party
        parties = db.query(Party).filter(Party.document_id == document_id).all()
        key_info["parties"] = [
            {"name": p.party_name, "type": p.party_type}
            for p in parties
        ]

        # Get key clause titles
        for chunk in chunks:
            if chunk.clause_title:
                key_info["key_clauses"].append({
                    "title": chunk.clause_title,
                    "number": chunk.clause_number,
                    "page": chunk.page_num
                })

        return key_info
    finally:
        db.close()


def generate_questions_for_document(document_id: str, key_info: Dict, use_llm: bool = True) -> List[Dict]:
    """Generate specific questions for a document based on its content"""
    filename = key_info.get("filename", "Unknown")

    # Base questions that are always relevant
    base_questions = []

    # Document-specific questions based on extracted info
    if key_info.get("effective_date"):
        base_questions.append({
            "question": f"What is the effective date of the {filename} NDA?",
            "document_id": document_id,
            "expected_type": "date",
            "verification_hint": f"Check the effective date clause in {filename}"
        })

    if key_info.get("term_months"):
        base_questions.append({
            "question": f"What is the term (duration) of the {filename} NDA in months?",
            "document_id": document_id,
            "expected_type": "number",
            "verification_hint": f"Check the term clause in {filename}"
        })

    if key_info.get("survival_months"):
        base_questions.append({
            "question": f"What is the survival period after expiration for the {filename} NDA in months?",
            "document_id": document_id,
            "expected_type": "number",
            "verification_hint": f"Check the survival clause in {filename}"
        })

    if key_info.get("governing_law"):
        base_questions.append({
            "question": f"What is the governing law for the {filename} NDA?",
            "document_id": document_id,
            "expected_type": "location",
            "verification_hint": f"Check the governing law clause in {filename}"
        })

    if key_info.get("is_mutual") is not None:
        mutual_text = "mutual" if key_info.get("is_mutual") else "unilateral"
        base_questions.append({
            "question": f"Is the {filename} NDA a mutual or unilateral agreement?",
            "document_id": document_id,
            "expected_type": "boolean",
            "verification_hint": f"Check if both parties have obligations in {filename}"
        })

    # Questions about parties
    parties = key_info.get("parties", [])
    if parties:
        party_names = [p["name"] for p in parties]
        if len(party_names) >= 2:
            base_questions.append({
                "question": f"Who are the parties to the {filename} NDA?",
                "document_id": document_id,
                "expected_type": "list",
                "verification_hint": f"Check the parties section in {filename}"
            })

    # Questions about specific clauses
    key_clauses = key_info.get("key_clauses", [])
    # Limit to first 3 key clauses to keep total questions manageable
    for clause in key_clauses[:3]:
        clause_title = clause.get("title", "").strip()
        clause_num = clause.get("number", "")
        # Skip single-letter titles and very short titles
        if clause_title and len(clause_title) > 5:  # Skip very short titles
            # Generate a question about this clause
            base_questions.append({
                "question": f"What does the {clause_title} clause specify in the {filename} NDA?",
                "document_id": document_id,
                "expected_type": "definition",
                "verification_hint": f"Check clause {clause_num or 'N/A'} ({clause_title}) on page {clause.get('page', '?')} in {filename}",
                "expected_clause": clause_title,
                "expected_page": clause.get("page")
            })

    # Use LLM to generate additional contextual questions if available
    if use_llm:
        try:
            llm = get_llm_client()
            if llm:
                # Create a prompt for the LLM to generate document-specific questions
                prompt = f"""Based on the following NDA document information, generate 3-5 specific questions that can be answered by reading this document.

Document: {filename}
Key Information:
- Effective Date: {key_info.get('effective_date', 'Unknown')}
- Term: {key_info.get('term_months', 'Unknown')} months
- Survival: {key_info.get('survival_months', 'Unknown')} months
- Governing Law: {key_info.get('governing_law', 'Unknown')}
- Is Mutual: {key_info.get('is_mutual', 'Unknown')}
- Key Clauses: {', '.join([c.get('title', '') for c in key_clauses[:10]])}

Generate specific, verifiable questions that someone could answer by reading this exact document.
Return ONLY a JSON array of question strings, no other text.
Example format: ["Question 1?", "Question 2?", "Question 3?"]
"""
                response = llm.generate(prompt, max_tokens=200)

                # Parse LLM response (try to extract JSON array)
                try:
                    # Try to extract JSON from response
                    import re
                    json_match = re.search(r'\[.*\]', response, re.DOTALL)
                    if json_match:
                        llm_questions = json.loads(json_match.group())
                        for q in llm_questions[:5]:  # Limit to 5 LLM questions
                            base_questions.append({
                                "question": q,
                                "document_id": document_id,
                                "expected_type": "general",
                                "verification_hint": f"Review {filename} to verify this answer",
                                "generated_by": "llm"
                            })
                except:
                    pass  # If LLM response can't be parsed, continue with base questions
        except Exception as e:
            print(f"Warning: Could not generate LLM questions: {e}")

    return base_questions


def create_question_with_document(question_text: str, document_id: str, verification_hint: str = None,
                                   expected_clause: str = None, expected_page: int = None) -> str:
    """Create a competency question associated with a specific document"""
    db = get_db_session()
    try:
        question = CompetencyQuestion(
            question_text=question_text,
            category_id=None,
            document_id=document_id,
            verification_hint=verification_hint,
            expected_clause=expected_clause,
            expected_page=expected_page,
            created_by="script"
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        return str(question.id)
    finally:
        db.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate document-specific competency questions")
    parser.add_argument("--document-id", type=str, help="Generate questions for specific document only")
    parser.add_argument("--use-llm", action="store_true", default=True, help="Use LLM to generate additional questions")
    parser.add_argument("--no-llm", action="store_true", help="Don't use LLM, only base questions")
    parser.add_argument("--dry-run", action="store_true", help="Preview questions without creating them")
    parser.add_argument("--create", action="store_true", help="Create questions in database")

    args = parser.parse_args()

    use_llm = args.use_llm and not args.no_llm

    print("=" * 70)
    print("Document-Specific Question Generator")
    print("=" * 70)

    # Get documents
    if args.document_id:
        documents = [{"id": args.document_id}]
        print(f"\n📄 Generating questions for specific document: {args.document_id}")
    else:
        documents = get_processed_documents()
        print(f"\n📄 Found {len(documents)} processed documents")

    all_questions = []

    for doc_info in documents:
        document_id = doc_info["id"]
        filename = doc_info.get("filename", "Unknown")

        print(f"\n📋 Analyzing: {filename}")

        # Extract key information
        key_info = extract_key_info_from_document(document_id)
        key_info["filename"] = filename

        # Generate questions
        questions = generate_questions_for_document(document_id, key_info, use_llm=use_llm)

        print(f"   ✅ Generated {len(questions)} questions")

        for q in questions:
            q["document_id"] = document_id
            q["document_filename"] = filename
            all_questions.append(q)

    # Display questions
    print("\n" + "=" * 70)
    print(f"Generated {len(all_questions)} total questions")
    print("=" * 70)

    for i, q in enumerate(all_questions, 1):
        print(f"\n[{i}] {q['question']}")
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
                question_id = create_question_with_document(
                    question_text=q['question'],
                    document_id=q['document_id'],
                    verification_hint=q.get('verification_hint'),
                    expected_clause=q.get('expected_clause'),
                    expected_page=q.get('expected_page')
                )
                created_count += 1
                print(f"✅ Created: {q['question'][:60]}...")
            except Exception as e:
                print(f"❌ Failed to create question: {e}")

        print(f"\n✅ Created {created_count} questions")
    elif args.dry_run:
        print("\n🔍 DRY RUN - No questions created. Use --create to create them.")
    else:
        print("\n💡 Use --create to create these questions in the database")

    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)


if __name__ == "__main__":
    main()
