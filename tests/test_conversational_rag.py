#!/usr/bin/env python3
"""
Test script for conversational RAG responses
"""
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.answer_service import answer_service


async def test_conversational_question(question: str, document_id: str = None):
    """Test a conversational question"""
    print(f"\n{'='*80}")
    print(f"Question: {question}")
    if document_id:
        print(f"Document ID: {document_id[:8]}...")
    print(f"{'='*80}")
    
    try:
        filters = {"document_id": document_id} if document_id else None
        
        result = await answer_service.generate_answer(
            question=question,
            filters=filters,
            max_context_chunks=10
        )
        
        print(f"\n✅ Answer: {result.text}")
        print(f"📊 Confidence: {result.confidence:.2f}" if result.confidence else "📊 Confidence: N/A")
        if result.evaluation_reasoning:
            print(f"💭 Reasoning: {result.evaluation_reasoning}")
        print(f"📚 Citations: {len(result.citations)}")
        
        if result.citations:
            print("\nCitations:")
            for i, cit in enumerate(result.citations[:3], 1):
                print(f"  {i}. doc_id={cit.doc_id[:8]}..., clause={cit.clause_number}, page={cit.page_num}")
        
        return result
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run conversational RAG tests"""
    print("🧪 Testing Conversational RAG Responses")
    print("="*80)
    
    # Test questions - these should trigger conversational mode
    test_questions = [
        # Days until expiration
        "how many days until the faunc nda expires?",
        "how many days do we have left until the faunc nda expires?",
        
        # Months until expiration
        "how many months until the faunc nda expires?",
        
        # When does questions
        "when does the faunc nda expire?",
        "when does faunc and norris expire?",
        
        # Comparison questions
        "does faunc and norris expire in the same month?",
        "do faunc and norris expire in the same year?",
    ]
    
    # Try to find Fanuc document ID
    from api.services.document_finder import document_finder
    fanuc_doc_id = document_finder.find_best_document_match("faunc", use_fuzzy=True)
    if not fanuc_doc_id:
        fanuc_doc_id = document_finder.find_best_document_match("fanuc", use_fuzzy=True)
    
    if fanuc_doc_id:
        print(f"✅ Found Fanuc document: {fanuc_doc_id[:8]}...")
    else:
        print("⚠️  Could not find Fanuc document, testing without document filter")
    
    # Run tests
    results = []
    for question in test_questions:
        result = await test_conversational_question(question, fanuc_doc_id)
        results.append((question, result))
        await asyncio.sleep(1)  # Small delay between requests
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 Test Summary")
    print(f"{'='*80}")
    
    successful = sum(1 for _, r in results if r and r.text)
    total = len(results)
    
    print(f"✅ Successful: {successful}/{total}")
    
    for question, result in results:
        status = "✅" if result and result.text else "❌"
        answer_preview = result.text[:60] + "..." if result and result.text else "No answer"
        print(f"{status} {question[:50]:50} -> {answer_preview}")
    
    print(f"\n{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())

