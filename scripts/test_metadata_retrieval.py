#!/usr/bin/env python3
"""
Test script to validate metadata-first retrieval (Phase 1)
Tests that structured questions are answered from metadata when available
"""
import os
import sys
import asyncio
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import CompetencyQuestion, DocumentMetadata, Party
from api.services.metadata_service import metadata_service
from api.services.answer_service import answer_service


async def test_metadata_retrieval():
    """Test that metadata-first retrieval works correctly"""
    print("=" * 80)
    print("METADATA-FIRST RETRIEVAL VALIDATION TEST")
    print("=" * 80)
    
    db = get_db_session()
    try:
        # Get questions that should be answerable from metadata
        questions = db.query(CompetencyQuestion).filter(
            CompetencyQuestion.is_active == True,
            CompetencyQuestion.document_id.isnot(None)
        ).all()
        
        print(f"\nTesting {len(questions)} questions with document_id filters...")
        
        metadata_tests = []
        chunk_retrieval_tests = []
        
        for question in questions:
            filters = {"document_id": str(question.document_id)}
            
            # Check if metadata exists for this document
            metadata = db.query(DocumentMetadata).filter(
                DocumentMetadata.document_id == question.document_id
            ).first()
            
            if not metadata:
                continue
            
            # Test answer generation
            answer_obj = await answer_service.generate_answer(
                question=question.question_text,
                filters=filters,
                max_context_chunks=30
            )
            
            # Detect if answer came from metadata (1 citation, short excerpt)
            is_metadata = (
                len(answer_obj.citations) == 1 and
                answer_obj.citations[0].excerpt and
                len(answer_obj.citations[0].excerpt) < 200
            )
            
            # Check accuracy
            expected = question.expected_answer_text.lower().strip() if question.expected_answer_text else ""
            actual = answer_obj.text.lower().strip() if answer_obj.text else ""
            
            accuracy = None
            if expected and actual:
                if expected == actual:
                    accuracy = 1.0
                elif expected in actual or actual in expected:
                    accuracy = 0.9
                else:
                    expected_words = set(expected.split())
                    actual_words = set(actual.split())
                    if expected_words and actual_words:
                        overlap = len(expected_words & actual_words)
                        accuracy = overlap / max(len(expected_words), len(actual_words))
            
            result = {
                "question": question.question_text,
                "expected": question.expected_answer_text,
                "actual": answer_obj.text,
                "is_metadata": is_metadata,
                "accuracy": accuracy,
                "citations_count": len(answer_obj.citations)
            }
            
            if is_metadata:
                metadata_tests.append(result)
            else:
                chunk_retrieval_tests.append(result)
        
        # Print results
        print(f"\n{'='*80}")
        print("METADATA-FIRST RESULTS")
        print(f"{'='*80}")
        print(f"Total questions tested: {len(metadata_tests) + len(chunk_retrieval_tests)}")
        print(f"Metadata answers: {len(metadata_tests)} ({len(metadata_tests)/(len(metadata_tests)+len(chunk_retrieval_tests))*100:.1f}%)")
        print(f"Chunk retrieval answers: {len(chunk_retrieval_tests)} ({len(chunk_retrieval_tests)/(len(metadata_tests)+len(chunk_retrieval_tests))*100:.1f}%)")
        
        if metadata_tests:
            metadata_accuracy = sum(r['accuracy'] or 0 for r in metadata_tests) / len(metadata_tests)
            metadata_passed = sum(1 for r in metadata_tests if r['accuracy'] and r['accuracy'] >= 0.7)
            print(f"\nMetadata-First Performance:")
            print(f"  Pass Rate: {metadata_passed}/{len(metadata_tests)} ({metadata_passed/len(metadata_tests)*100:.1f}%)")
            print(f"  Average Accuracy: {metadata_accuracy:.1%}")
            
            if metadata_accuracy >= 0.95:
                print(f"  ✅ SUCCESS: Metadata accuracy ({metadata_accuracy:.1%}) meets 95%+ goal!")
            else:
                print(f"  ⚠️  Metadata accuracy ({metadata_accuracy:.1%}) below 95% goal")
        
        if chunk_retrieval_tests:
            chunk_accuracy = sum(r['accuracy'] or 0 for r in chunk_retrieval_tests) / len(chunk_retrieval_tests)
            chunk_passed = sum(1 for r in chunk_retrieval_tests if r['accuracy'] and r['accuracy'] >= 0.7)
            print(f"\nChunk Retrieval Performance:")
            print(f"  Pass Rate: {chunk_passed}/{len(chunk_retrieval_tests)} ({chunk_passed/len(chunk_retrieval_tests)*100:.1f}%)")
            print(f"  Average Accuracy: {chunk_accuracy:.1%}")
        
        # Show examples
        print(f"\n{'='*80}")
        print("METADATA-FIRST EXAMPLES")
        print(f"{'='*80}")
        for i, result in enumerate(metadata_tests[:5], 1):
            print(f"\n{i}. Question: {result['question'][:60]}...")
            print(f"   Expected: {result['expected']}")
            print(f"   Actual: {result['actual']}")
            print(f"   Accuracy: {result['accuracy']:.1%}" if result['accuracy'] else "   Accuracy: N/A")
            print(f"   Citations: {result['citations_count']}")
        
        print(f"\n{'='*80}")
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_metadata_retrieval())

