#!/usr/bin/env python3
"""
Golden question test suite for RAG quality evaluation.
Tests document-specific queries to ensure correct document retrieval.
"""
import sys
import os
import asyncio
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.answer_service import answer_service
from api.db import get_db_session
from api.db.schema import Document


# Golden questions with expected answers
GOLDEN_QUESTIONS = [
    {
        "question": "What is the governing state of Vallen Distribution, Inc.?",
        "expected_answer": "Delaware",
        "document_hint": "Vallen Distribution",
        "test_variations": [
            "What is the governing state of Vallen?",
            "What is the governing law for Vallen Distribution?",
            "Vallen Distribution governing state",
        ]
    },
    {
        "question": "What is the effective date of Norris Cylinder Company?",
        "expected_answer": None,  # Will check if answer is found
        "document_hint": "Norris Cylinder",
        "test_variations": [
            "What is the effective date of Norris?",
            "Norris Cylinder effective date",
        ]
    },
    {
        "question": "What is the term of the NDA for KGS Fire & Security B.V.?",
        "expected_answer": "3 years",
        "document_hint": "KGS Fire",
        "test_variations": [
            "What is the term for KGS?",
            "KGS Fire term",
        ]
    },
    {
        "question": "Who are the parties to the NDA for Boston Green Company, Inc.?",
        "expected_answer": None,  # Will check if parties are mentioned
        "document_hint": "Boston Green",
        "test_variations": [
            "Who are the parties for Boston Green?",
            "Boston Green parties",
        ]
    },
    {
        "question": "Is the NDA mutual or unilateral for Central Coating Technologies, Inc.?",
        "expected_answer": None,  # Will check if mutual/unilateral is mentioned
        "document_hint": "Central Coating",
        "test_variations": [
            "Is Central Coating mutual?",
            "Central Coating mutual or unilateral",
        ]
    },
]


async def test_question(question: str, expected_answer: str = None, document_hint: str = None) -> Dict:
    """Test a single question and return results with chunk analysis."""
    print(f"\n{'='*80}")
    print(f"Question: {question}")
    if expected_answer:
        print(f"Expected: {expected_answer}")
    if document_hint:
        print(f"Document hint: {document_hint}")
    print(f"{'='*80}")
    
    try:
        # Get answer
        result = await answer_service.generate_answer(
            question=question,
            max_context_chunks=10
        )
        
        answer = result.text.strip()
        citations = result.citations
        
        # Analyze chunks - find which chunks contain the answer
        chunks_with_answer = []
        chunks_without_answer = []
        
        if expected_answer:
            expected_lower = expected_answer.lower()
            answer_lower = answer.lower()
            search_terms = expected_lower.split() + answer_lower.split()
            search_terms = [t for t in search_terms if len(t) > 2]  # Filter short words
            
            for citation in citations:
                excerpt_lower = citation.excerpt.lower() if citation.excerpt else ""
                contains_answer = any(term in excerpt_lower for term in search_terms if len(term) > 2)
                
                chunk_info = {
                    "doc_id": citation.doc_id[:8] + "...",
                    "clause": citation.clause_number,
                    "page": citation.page_num,
                    "excerpt_preview": citation.excerpt[:150] + "..." if citation.excerpt and len(citation.excerpt) > 150 else citation.excerpt,
                    "contains_answer": contains_answer,
                    "excerpt_length": len(citation.excerpt) if citation.excerpt else 0
                }
                
                if contains_answer:
                    chunks_with_answer.append(chunk_info)
                else:
                    chunks_without_answer.append(chunk_info)
        
        # Check if correct document was retrieved
        correct_doc_found = False
        correct_doc_name = None
        if document_hint:
            for citation in citations[:3]:  # Check top 3 citations
                # Get document name from database
                db = get_db_session()
                try:
                    doc = db.query(Document).filter(Document.id == citation.doc_id).first()
                    if doc and document_hint.lower() in doc.filename.lower():
                        correct_doc_found = True
                        correct_doc_name = doc.filename
                        print(f"✅ Correct document found: {doc.filename}")
                        break
                finally:
                    db.close()
        
        # Check answer quality
        answer_correct = False
        if expected_answer:
            answer_lower = answer.lower()
            expected_lower = expected_answer.lower()
            if expected_lower in answer_lower or answer_lower in expected_lower:
                answer_correct = True
            elif any(word in answer_lower for word in expected_lower.split()):
                answer_correct = True  # Partial match
        
        print(f"\nAnswer: {answer}")
        print(f"Citations: {len(citations)}")
        print(f"Correct document found: {correct_doc_found}")
        print(f"Answer correct: {answer_correct}")
        
        # Print chunk analysis
        if expected_answer:
            print(f"\n📊 Chunk Analysis:")
            print(f"  Chunks WITH answer: {len(chunks_with_answer)}")
            for i, chunk in enumerate(chunks_with_answer[:3], 1):
                print(f"    ✅ {i}. doc={chunk['doc_id']}, clause={chunk['clause']}, page={chunk['page']}")
                print(f"       Preview: {chunk['excerpt_preview']}")
            
            print(f"  Chunks WITHOUT answer: {len(chunks_without_answer)}")
            for i, chunk in enumerate(chunks_without_answer[:3], 1):
                print(f"    ❌ {i}. doc={chunk['doc_id']}, clause={chunk['clause']}, page={chunk['page']}")
                print(f"       Preview: {chunk['excerpt_preview']}")
        
        return {
            "question": question,
            "answer": answer,
            "expected_answer": expected_answer,
            "answer_correct": answer_correct,
            "correct_doc_found": correct_doc_found,
            "correct_doc_name": correct_doc_name,
            "num_citations": len(citations),
            "top_citation_doc_id": citations[0].doc_id if citations else None,
            "chunks_with_answer": chunks_with_answer,
            "chunks_without_answer": chunks_without_answer,
            "chunk_quality": {
                "total_chunks": len(citations),
                "chunks_with_answer": len(chunks_with_answer),
                "chunks_without_answer": len(chunks_without_answer),
                "quality_score": len(chunks_with_answer) / len(citations) if citations else 0
            }
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "question": question,
            "error": str(e),
            "answer_correct": False,
            "correct_doc_found": False,
        }


async def run_all_tests():
    """Run all golden question tests."""
    print("="*80)
    print("RAG GOLDEN QUESTION TEST SUITE")
    print("="*80)
    
    results = []
    
    for test_case in GOLDEN_QUESTIONS:
        # Test main question
        result = await test_question(
            question=test_case["question"],
            expected_answer=test_case.get("expected_answer"),
            document_hint=test_case.get("document_hint")
        )
        results.append(result)
        
        # Test variations
        for variation in test_case.get("test_variations", []):
            var_result = await test_question(
                question=variation,
                expected_answer=test_case.get("expected_answer"),
                document_hint=test_case.get("document_hint")
            )
            var_result["is_variation"] = True
            var_result["original_question"] = test_case["question"]
            results.append(var_result)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total = len(results)
    correct_answers = sum(1 for r in results if r.get("answer_correct", False))
    correct_docs = sum(1 for r in results if r.get("correct_doc_found", False))
    
    # Chunk quality analysis
    chunk_quality_scores = [r.get("chunk_quality", {}).get("quality_score", 0) for r in results if r.get("chunk_quality")]
    avg_chunk_quality = sum(chunk_quality_scores) / len(chunk_quality_scores) if chunk_quality_scores else 0
    
    print(f"Total questions: {total}")
    print(f"Correct answers: {correct_answers}/{total} ({100*correct_answers/total:.1f}%)")
    print(f"Correct documents found: {correct_docs}/{total} ({100*correct_docs/total:.1f}%)")
    print(f"Average chunk quality: {avg_chunk_quality:.1%} (chunks with answer / total chunks)")
    
    # Show worst performing questions
    print(f"\n📊 Worst Chunk Quality Questions:")
    results_with_quality = [r for r in results if r.get("chunk_quality")]
    worst = sorted(results_with_quality, key=lambda x: x.get("chunk_quality", {}).get("quality_score", 1))[:5]
    for r in worst:
        quality = r.get("chunk_quality", {})
        print(f"  - {r['question'][:60]}...")
        print(f"    Quality: {quality.get('quality_score', 0):.1%} ({quality.get('chunks_with_answer', 0)}/{quality.get('total_chunks', 0)} chunks)")
    
    # Save results
    output_file = Path(__file__).parent.parent.parent / "testing" / "rag_test_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_all_tests())

