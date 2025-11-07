#!/usr/bin/env python3
"""
Comprehensive RAG Test Suite - Document-Specific Questions
Tests RAG system with questions extracted from actual PDF documents
Each question is specific to a real NDA document and asks about actual information
"""
import sys
import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from api.services.answer_service import answer_service
from api.services.answer_evaluator import answer_evaluator


# Load document-specific questions
def load_document_specific_questions() -> List[Dict[str, Any]]:
    """Load document-specific questions from JSON file"""
    questions_file = Path(__file__).parent.parent / 'document_specific_questions.json'
    
    if not questions_file.exists():
        print(f"❌ Questions file not found: {questions_file}")
        print("   Run generate_document_specific_questions.py first")
        return []
    
    with open(questions_file, 'r') as f:
        questions = json.load(f)
    
    return questions


# Group questions by category for better organization
def organize_questions_by_category(questions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Organize questions by category"""
    by_category = {}
    for q in questions:
        cat = q.get('category', 'Other')
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(q)
    return by_category


async def run_test_case(test_case: Dict[str, Any], test_num: int, total: int) -> Dict[str, Any]:
    """
    Run a single test case
    
    Args:
        test_case: Test case dict with question, expected_contains, min_confidence, etc.
        test_num: Test number for display
        total: Total number of tests
        
    Returns:
        Dict with test results
    """
    question = test_case['question']
    expected_contains = test_case.get('expected_contains', [])
    min_confidence = test_case.get('min_confidence', 0.7)
    description = test_case.get('description', '')
    category = test_case.get('category', 'Other')
    document_id = test_case.get('document_id')
    
    print(f"\n[{test_num}/{total}] {category}: {description}")
    print(f"  Q: {question}")
    
    try:
        # Generate answer
        answer_obj = await answer_service.generate_answer(question)
        actual_answer = answer_obj.text
        system_confidence = answer_obj.confidence or 0.0
        
        # Use LLM-based evaluation
        evaluation = await answer_evaluator.evaluate_answer(
            question=question,
            actual_answer=actual_answer,
            expected_answer=None,  # We'll use expected_contains for matching
            context_chunks=None
        )
        
        llm_confidence = evaluation.get('confidence', 0.0)
        llm_correctness = evaluation.get('correctness', False)
        llm_reasoning = evaluation.get('reasoning', '')
        
        # Check if answer contains expected content
        answer_lower = actual_answer.lower()
        contains_expected = False
        matched_terms = []
        
        for expected_term in expected_contains:
            # For date formats (YYYY-MM), also check for full dates
            if '-' in expected_term and len(expected_term) == 7:  # YYYY-MM format
                year_month = expected_term
                # Check if year-month appears in answer (e.g., "2025-09" or "September 2025" or "2025-09-14")
                if year_month in answer_lower or year_month.replace('-', ' ') in answer_lower:
                    contains_expected = True
                    matched_terms.append(expected_term)
                # Also check for month name + year (e.g., "September 2025")
                year = year_month.split('-')[0]
                month_num = year_month.split('-')[1]
                month_names = {
                    '01': ['january', 'jan'],
                    '02': ['february', 'feb'],
                    '03': ['march', 'mar'],
                    '04': ['april', 'apr'],
                    '05': ['may'],
                    '06': ['june', 'jun'],
                    '07': ['july', 'jul'],
                    '08': ['august', 'aug'],
                    '09': ['september', 'sept', 'sep'],
                    '10': ['october', 'oct'],
                    '11': ['november', 'nov'],
                    '12': ['december', 'dec']
                }
                if month_num in month_names:
                    for month_name in month_names[month_num]:
                        if month_name in answer_lower and year in answer_lower:
                            contains_expected = True
                            matched_terms.append(expected_term)
                            break
            else:
                # Regular string matching
                if expected_term.lower() in answer_lower:
                    contains_expected = True
                    matched_terms.append(expected_term)
        
        # Determine pass/fail
        # Pass if: LLM says correct OR (contains expected AND confidence high enough)
        passed = (
            llm_correctness or 
            (contains_expected and (llm_confidence >= min_confidence or system_confidence >= min_confidence))
        )
        
        result = {
            'question': question,
            'category': category,
            'description': description,
            'document_id': document_id,
            'expected_contains': expected_contains,
            'actual_answer': actual_answer,
            'system_confidence': system_confidence,
            'llm_confidence': llm_confidence,
            'llm_correctness': llm_correctness,
            'llm_reasoning': llm_reasoning,
            'contains_expected': contains_expected,
            'matched_terms': matched_terms,
            'passed': passed,
            'min_confidence': min_confidence
        }
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  A: {actual_answer[:150]}...")
        print(f"  {status} | System: {system_confidence:.2f} | LLM: {llm_confidence:.2f} | Contains: {matched_terms}")
        
        return result
        
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            'question': question,
            'category': category,
            'description': description,
            'document_id': document_id,
            'error': str(e),
            'passed': False
        }


async def run_all_tests():
    """Run all document-specific tests"""
    print("=" * 80)
    print("Comprehensive RAG Test Suite - Document-Specific Questions")
    print("=" * 80)
    
    # Load questions
    questions = load_document_specific_questions()
    
    if not questions:
        print("No questions to test. Exiting.")
        return
    
    print(f"\nLoaded {len(questions)} document-specific questions")
    
    # Organize by category
    by_category = organize_questions_by_category(questions)
    print("\nQuestions by category:")
    for cat, cat_questions in sorted(by_category.items()):
        print(f"  {cat}: {len(cat_questions)}")
    
    # Run tests
    print("\n" + "=" * 80)
    print("Running Tests...")
    print("=" * 80)
    
    results = []
    total = len(questions)
    
    for i, test_case in enumerate(questions, 1):
        result = await run_test_case(test_case, i, total)
        results.append(result)
    
    # Calculate statistics
    print("\n" + "=" * 80)
    print("Test Results Summary")
    print("=" * 80)
    
    total_tests = len(results)
    passed = sum(1 for r in results if r.get('passed', False))
    failed = total_tests - passed
    pass_rate = (passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\nOverall Results:")
    print(f"  Total Tests: {total_tests}")
    print(f"  Passed: {passed} ({pass_rate:.1f}%)")
    print(f"  Failed: {failed}")
    
    # Results by category
    print(f"\nResults by Category:")
    category_stats = {}
    for result in results:
        cat = result.get('category', 'Other')
        if cat not in category_stats:
            category_stats[cat] = {'total': 0, 'passed': 0}
        category_stats[cat]['total'] += 1
        if result.get('passed', False):
            category_stats[cat]['passed'] += 1
    
    for cat in sorted(category_stats.keys()):
        stats = category_stats[cat]
        cat_pass_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"  {cat}: {stats['passed']}/{stats['total']} ({cat_pass_rate:.1f}%)")
    
    # Failed tests
    failed_tests = [r for r in results if not r.get('passed', False)]
    if failed_tests:
        print(f"\n❌ Failed Tests ({len(failed_tests)}):")
        for result in failed_tests[:10]:  # Show first 10
            print(f"  - {result.get('category', 'Other')}: {result.get('question', 'Unknown')[:80]}...")
        if len(failed_tests) > 10:
            print(f"  ... and {len(failed_tests) - 10} more")
    
    # Save results
    results_file = Path(__file__).parent.parent / 'results' / f'comprehensive_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    results_file.parent.mkdir(exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_tests': total_tests,
            'passed': passed,
            'failed': failed,
            'pass_rate': pass_rate,
            'category_stats': category_stats,
            'results': results
        }, f, indent=2)
    
    print(f"\n✅ Results saved to {results_file}")
    
    # Validation against 95% goal
    print("\n" + "=" * 80)
    if pass_rate >= 95.0:
        print("✅ SUCCESS: Pass rate meets 95%+ goal!")
    else:
        print(f"⚠️  WARNING: Pass rate ({pass_rate:.1f}%) is below 95% goal")
        print(f"   Need to improve by {95.0 - pass_rate:.1f} percentage points")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(run_all_tests())
