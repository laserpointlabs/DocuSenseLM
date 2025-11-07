#!/usr/bin/env python3
"""
Comprehensive test suite for query flexibility
Tests variations, misspellings, alternate phrasings, and date queries
"""
import os
import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.answer_service import answer_service
from api.services.query_normalizer import query_normalizer
from api.services.document_finder import document_finder


# Test cases with variations
TEST_CASES = [
    {
        "category": "Company Name Variations",
        "base_question": "What is the governing state of Vallen Distribution, Inc.?",
        "variations": [
            "What is the governing state of Vallen Distribution, Inc.?",  # Exact
            "What is the governing state of Vallen?",  # Partial
            "What is the governing state of Vallen Industries?",  # Wrong suffix
            "What is the governing state of Valen?",  # Misspelling (1 char)
            "What is the governing state of Vallen Dist?",  # Abbreviation
            "What is the governing law for Vallen?",  # Synonym
            "What jurisdiction applies to Vallen?",  # Different phrasing
        ]
    },
    {
        "category": "Misspellings",
        "base_question": "What is the effective date?",
        "variations": [
            "What is the effective date?",  # Correct
            "What is the effecive date?",  # Missing 't'
            "What is the efective date?",  # Missing 'f'
            "What is the effective dat?",  # Missing 'e'
            "What is the efecive date?",  # Multiple errors
        ]
    },
    {
        "category": "Poorly Worded Queries",
        "base_question": "What is the term of the NDA?",
        "variations": [
            "What is the term of the NDA?",  # Well-formed
            "what nda term",  # No question words
            "term how long",  # Fragmented
            "can you tell me the term",  # Filler words
            "i want to know the duration",  # Filler words
            "please tell me how long is it",  # Very informal
        ]
    },
    {
        "category": "Date Range Queries",
        "base_question": "What NDAs were created in January 2025?",
        "variations": [
            "What NDAs were created in January 2025?",
            "What NDAs were created in Jan 2025?",
            "What NDAs were signed in January 2025?",
            "What agreements were created in January 2025?",
            "Show me NDAs from January 2025",
            "NDAs in January 2025",
        ]
    },
    {
        "category": "Synonym Variations",
        "base_question": "What is the governing law?",
        "variations": [
            "What is the governing law?",
            "What is the governing state?",
            "What jurisdiction applies?",
            "What law governs?",
            "Which state's law?",
        ]
    },
    {
        "category": "Term Variations",
        "base_question": "What is the term?",
        "variations": [
            "What is the term?",
            "What is the duration?",
            "How long is it?",
            "What is the length?",
            "When does it expire?",
        ]
    },
]


async def test_query_variation(base_question: str, variation: str, document_id: str = None) -> Dict:
    """Test a single query variation"""
    try:
        filters = {"document_id": document_id} if document_id else None
        
        result = await answer_service.generate_answer(
            question=variation,
            filters=filters
        )
        
        return {
            "variation": variation,
            "answer": result.text,
            "confidence": result.confidence,
            "citations_count": len(result.citations),
            "success": result.text and "cannot find" not in result.text.lower(),
            "error": None
        }
    except Exception as e:
        return {
            "variation": variation,
            "answer": None,
            "confidence": None,
            "citations_count": 0,
            "success": False,
            "error": str(e)
        }


async def run_flexibility_tests():
    """Run comprehensive flexibility tests"""
    print("=" * 80)
    print("QUERY FLEXIBILITY TEST SUITE")
    print("=" * 80)
    print()
    
    # Get a test document ID
    from api.db import get_db_session
    from api.db.schema import Document, DocumentStatus
    
    db = get_db_session()
    try:
        test_doc = db.query(Document).filter(
            Document.status == DocumentStatus.PROCESSED
        ).first()
        test_doc_id = str(test_doc.id) if test_doc else None
    finally:
        db.close()
    
    if not test_doc_id:
        print("❌ No processed documents found. Cannot run tests.")
        return
    
    print(f"Using test document: {test_doc_id[:8]}...")
    print()
    
    all_results = []
    total_tests = 0
    passed_tests = 0
    
    for test_group in TEST_CASES:
        category = test_group["category"]
        base_question = test_group["base_question"]
        variations = test_group["variations"]
        
        print(f"📋 Category: {category}")
        print(f"   Base question: {base_question}")
        print()
        
        category_results = []
        for variation in variations:
            total_tests += 1
            result = await test_query_variation(base_question, variation, test_doc_id)
            category_results.append(result)
            
            status = "✅" if result["success"] else "❌"
            print(f"   {status} {variation[:60]}...")
            if result["success"]:
                print(f"      Answer: {result['answer'][:60]}... (Conf: {result['confidence']:.2f})")
                passed_tests += 1
            else:
                print(f"      Failed: {result.get('error', 'No answer found')}")
            print()
        
        all_results.append({
            "category": category,
            "base_question": base_question,
            "results": category_results
        })
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total variations tested: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Pass rate: {passed_tests/total_tests*100:.1f}%")
    print()
    
    # Category breakdown
    print("Category Breakdown:")
    for group_result in all_results:
        category = group_result["category"]
        results = group_result["results"]
        passed = sum(1 for r in results if r["success"])
        total = len(results)
        print(f"  {category}: {passed}/{total} ({passed/total*100:.1f}%)")
    
    # Save results
    output_file = f"reports/flexibility_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("reports", exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests,
                "pass_rate": passed_tests/total_tests*100
            },
            "results": all_results
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_flexibility_tests())

