#!/usr/bin/env python3
"""
Golden question test with chunk analysis
"""
import sys
import asyncio
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.answer_service import answer_service
from api.db import get_db_session
from api.db.schema import Document

GOLDEN_QUESTIONS = [
    {
        "question": "What is the governing state of Vallen Distribution, Inc.?",
        "expected_answer": "Delaware",
        "document_hint": "Vallen Distribution",
    },
    {
        "question": "What is the governing state of Vallen?",
        "expected_answer": "Delaware",
        "document_hint": "Vallen Distribution",
    },
    {
        "question": "What is the term of the NDA for KGS Fire & Security B.V.?",
        "expected_answer": "3 years",
        "document_hint": "KGS Fire",
    },
]

async def test_question(question: str, expected_answer: str = None, document_hint: str = None):
    """Test a single question with chunk analysis."""
    print(f"\n{'='*80}")
    print(f"Question: {question}")
    print(f"Expected: {expected_answer}")
    print(f"{'='*80}")
    
    try:
        result = await answer_service.generate_answer(question=question, max_context_chunks=10)
        answer = result.text.strip()
        citations = result.citations
        
        # Analyze chunks
        chunks_with_answer = []
        chunks_without_answer = []
        
        if expected_answer:
            expected_lower = expected_answer.lower()
            answer_lower = answer.lower()
            search_terms = expected_lower.split() + answer_lower.split()
            search_terms = [t for t in search_terms if len(t) > 2]
            
            for citation in citations:
                excerpt_lower = citation.excerpt.lower() if citation.excerpt else ""
                contains_answer = any(term in excerpt_lower for term in search_terms if len(term) > 2)
                
                chunk_info = {
                    "doc_id": citation.doc_id[:8] + "...",
                    "clause": citation.clause_number,
                    "page": citation.page_num,
                    "excerpt": citation.excerpt[:200] + "..." if citation.excerpt and len(citation.excerpt) > 200 else citation.excerpt,
                    "contains_answer": contains_answer,
                }
                
                if contains_answer:
                    chunks_with_answer.append(chunk_info)
                else:
                    chunks_without_answer.append(chunk_info)
        
        # Check document
        correct_doc_found = False
        if document_hint:
            for citation in citations[:3]:
                db = get_db_session()
                try:
                    doc = db.query(Document).filter(Document.id == citation.doc_id).first()
                    if doc and document_hint.lower() in doc.filename.lower():
                        correct_doc_found = True
                        print(f"✅ Correct document: {doc.filename}")
                        break
                finally:
                    db.close()
        
        # Check answer
        answer_correct = False
        if expected_answer:
            answer_lower = answer.lower()
            expected_lower = expected_answer.lower()
            if expected_lower in answer_lower or answer_lower in expected_lower:
                answer_correct = True
            elif any(word in answer_lower for word in expected_lower.split()):
                answer_correct = True
        
        print(f"\nAnswer: {answer}")
        print(f"✅ Correct: {answer_correct}")
        print(f"✅ Correct doc: {correct_doc_found}")
        print(f"\n📊 Chunk Analysis:")
        print(f"  Total chunks: {len(citations)}")
        print(f"  Chunks WITH answer: {len(chunks_with_answer)}")
        print(f"  Chunks WITHOUT answer: {len(chunks_without_answer)}")
        
        if chunks_with_answer:
            print(f"\n  ✅ Chunks WITH answer:")
            for i, chunk in enumerate(chunks_with_answer[:3], 1):
                print(f"    {i}. doc={chunk['doc_id']}, clause={chunk['clause']}, page={chunk['page']}")
                print(f"       {chunk['excerpt']}")
        
        if chunks_without_answer:
            print(f"\n  ❌ Chunks WITHOUT answer (showing first 3):")
            for i, chunk in enumerate(chunks_without_answer[:3], 1):
                print(f"    {i}. doc={chunk['doc_id']}, clause={chunk['clause']}, page={chunk['page']}")
                print(f"       {chunk['excerpt']}")
        
        return {
            "question": question,
            "answer": answer,
            "expected_answer": expected_answer,
            "answer_correct": answer_correct,
            "correct_doc_found": correct_doc_found,
            "chunks_with_answer": len(chunks_with_answer),
            "chunks_without_answer": len(chunks_without_answer),
            "total_chunks": len(citations),
        }
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"question": question, "error": str(e)}

async def main():
    print("="*80)
    print("GOLDEN QUESTION TEST WITH CHUNK ANALYSIS")
    print("="*80)
    
    results = []
    for test in GOLDEN_QUESTIONS:
        result = await test_question(
            question=test["question"],
            expected_answer=test.get("expected_answer"),
            document_hint=test.get("document_hint")
        )
        results.append(result)
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    total = len(results)
    correct = sum(1 for r in results if r.get("answer_correct", False))
    correct_docs = sum(1 for r in results if r.get("correct_doc_found", False))
    
    total_chunks = sum(r.get("total_chunks", 0) for r in results)
    chunks_with_answer = sum(r.get("chunks_with_answer", 0) for r in results)
    
    print(f"Total questions: {total}")
    print(f"Correct answers: {correct}/{total} ({100*correct/total:.1f}%)")
    print(f"Correct documents: {correct_docs}/{total} ({100*correct_docs/total:.1f}%)")
    print(f"Chunk quality: {chunks_with_answer}/{total_chunks} chunks contain answer ({100*chunks_with_answer/total_chunks:.1f}%)")
    
    # Save results
    results_path = Path(__file__).parent.parent / "testing" / "rag_test_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_path}")

if __name__ == "__main__":
    asyncio.run(main())


