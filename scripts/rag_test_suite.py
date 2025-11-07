#!/usr/bin/env python3
"""
RAG Test Suite - Repeatable testing with configuration support
Tests RAG system with different configurations and stores results for comparison
"""
import os
import sys
import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import CompetencyQuestion, TestRun, DocumentStatus
from api.services.answer_service import answer_service


def get_test_configuration() -> Dict:
    """Get current test configuration from environment variables"""
    return {
        "rag_strategy": os.getenv("RAG_STRATEGY", "single_query"),
        "hybrid_bm25_weight": float(os.getenv("HYBRID_BM25_WEIGHT", "0.5")),
        "hybrid_vector_weight": float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.5")),
        "rrf_k": int(os.getenv("RRF_K", "60")),
        "max_context_chunks": int(os.getenv("MAX_CONTEXT_CHUNKS", "30")),
        "context_window": int(os.getenv("OLLAMA_CONTEXT_LENGTH") or os.getenv("CONTEXT_WINDOW")),
        "model": os.getenv("OLLAMA_MODEL") or os.getenv("LLM_MODEL"),
        "chunk_quality_threshold": float(os.getenv("CHUNK_QUALITY_THRESHOLD", "0.3")),
        "metadata_first": True,  # Phase 1: Metadata-first is enabled
        "contextual_embeddings": True,  # Phase 3: Contextual embeddings enabled
        "query_transformation": True,  # Phase 4: Query transformation enabled
    }


async def test_question(
    question: CompetencyQuestion,
    config: Dict,
    max_context_chunks: Optional[int] = None
) -> Dict:
    """Test a single question and return results with chunk analysis"""
    import logging
    logger = logging.getLogger(__name__)
    
    start_time = datetime.now()
    
    try:
        # Set environment variables for this test
        os.environ["RAG_STRATEGY"] = config["rag_strategy"]
        os.environ["HYBRID_BM25_WEIGHT"] = str(config["hybrid_bm25_weight"])
        os.environ["HYBRID_VECTOR_WEIGHT"] = str(config["hybrid_vector_weight"])
        os.environ["RRF_K"] = str(config["rrf_k"])
        
        # Get filters if question is document-specific
        filters = None
        if question.document_id:
            filters = {"document_id": str(question.document_id)}
        
        # Generate answer
        result = await answer_service.generate_answer(
            question=question.question_text,
            filters=filters,
            max_context_chunks=max_context_chunks or config["max_context_chunks"]
        )
        
        end_time = datetime.now()
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        answer = result.text.strip() if result.text else ""
        citations = result.citations
        confidence = result.confidence  # Get confidence from answer
        evaluation_reasoning = result.evaluation_reasoning  # Get reasoning from answer
        
        # Analyze chunks - find which contain the answer
        chunks_with_answer = 0
        chunks_without_answer = 0
        
        expected = question.expected_answer_text.lower().strip() if question.expected_answer_text else ""
        if expected and answer:
            answer_lower = answer.lower()
            search_terms = expected.split() + answer_lower.split()
            search_terms = [t for t in search_terms if len(t) > 2]
            
            for citation in citations:
                excerpt_lower = citation.excerpt.lower() if citation.excerpt else ""
                contains_answer = any(term in excerpt_lower for term in search_terms if len(term) > 2)
                if contains_answer:
                    chunks_with_answer += 1
                else:
                    chunks_without_answer += 1
        
        # Calculate accuracy using LLM-based evaluation (semantic comparison)
        accuracy_score = None
        if expected and answer:
            # Use LLM to evaluate answer correctness
            from api.services.answer_evaluator import answer_evaluator
            try:
                eval_result = await answer_evaluator.evaluate_answer(
                    question=question.question_text,
                    actual_answer=answer,
                    expected_answer=expected,
                    context_chunks=None  # Context not needed for comparison
                )
                # Use confidence as accuracy score
                accuracy_score = eval_result.get("confidence", 0.5)
                logger.info(f"LLM evaluation: confidence={accuracy_score:.2f}, reasoning={eval_result.get('reasoning', '')[:100]}")
            except Exception as e:
                logger.warning(f"LLM evaluation failed, using fallback: {e}")
                # Fallback to string matching
                expected_lower = expected.lower().strip()
                answer_lower = answer.lower().strip()
                
                if expected_lower == answer_lower:
                    accuracy_score = 1.0
                elif expected_lower in answer_lower or answer_lower in expected_lower:
                    accuracy_score = 0.9
                else:
                    expected_words = set(expected_lower.split())
                    actual_words = set(answer_lower.split())
                    if expected_words and actual_words:
                        overlap = len(expected_words & actual_words)
                        accuracy_score = overlap / max(len(expected_words), len(actual_words))
        
        # Detect if answer came from metadata (Phase 1 validation)
        # Metadata answers typically have 1 citation with minimal text
        is_metadata_answer = (
            len(citations) == 1 and 
            citations[0].excerpt and 
            len(citations[0].excerpt) < 200 and
            any(keyword in citations[0].excerpt.lower() for keyword in [
                'effective date', 'governing law', 'term', 'parties', 'mutual', 'unilateral'
            ])
        )
        
        # Detect if this is a cross-document query
        is_cross_document = any(term in question.question_text.lower() for term in [
            'compare', 'across all', 'all ndas', 'all documents', 'difference', 'different'
        ])
        
        chunk_quality = chunks_with_answer / len(citations) if citations else 0
        
        # Use question's confidence threshold if available, otherwise default to 0.7
        confidence_threshold = question.confidence_threshold if question.confidence_threshold else 0.7
        
        return {
            "question_id": str(question.id),
            "question_text": question.question_text,
            "expected_answer": question.expected_answer_text,
            "actual_answer": answer,
            "accuracy_score": accuracy_score,
            "confidence": confidence,  # Include confidence from answer service
            "evaluation_reasoning": evaluation_reasoning,  # Include reasoning
            "response_time_ms": response_time_ms,
            "citations_count": len(citations),
            "chunks_with_answer": chunks_with_answer,
            "chunks_without_answer": chunks_without_answer,
            "chunk_quality": chunk_quality,
            "is_metadata_answer": is_metadata_answer,
            "is_cross_document": is_cross_document,
            "passed": accuracy_score is not None and accuracy_score >= confidence_threshold,
            "configuration": config,
        }
    except Exception as e:
        logger.error(f"Error testing question {question.id}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "question_id": str(question.id),
            "question_text": question.question_text,
            "expected_answer": question.expected_answer_text,
            "actual_answer": None,
            "error": str(e),
            "accuracy_score": None,
            "response_time_ms": 0,
            "citations_count": 0,
            "chunks_with_answer": 0,
            "chunks_without_answer": 0,
            "chunk_quality": 0,
            "passed": False,
            "configuration": config,
        }


async def run_test_suite(
    config: Optional[Dict] = None,
    question_ids: Optional[List[str]] = None,
    max_questions: Optional[int] = None
) -> List[Dict]:
    """Run test suite with given configuration"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Set random seed for reproducibility
    random.seed(42)
    
    # Get configuration
    if config is None:
        config = get_test_configuration()
    
    logger.info(f"Running test suite with configuration: {config}")
    
    # Get questions from database
    db = get_db_session()
    try:
        query = db.query(CompetencyQuestion).filter(CompetencyQuestion.is_active == True)
        
        if question_ids:
            query = query.filter(CompetencyQuestion.id.in_(question_ids))
        
        questions = query.all()
        
        if max_questions:
            questions = questions[:max_questions]
        
        logger.info(f"Testing {len(questions)} questions")
    finally:
        db.close()
    
    # Run tests
    results = []
    for i, question in enumerate(questions, 1):
        logger.info(f"[{i}/{len(questions)}] Testing: {question.question_text[:60]}...")
        result = await test_question(question, config)
        results.append(result)
        
        # Save to database
        db = get_db_session()
        try:
            # Build citations data with configuration
            citations_data = []
            if result.get("actual_answer"):
                # Store configuration in first citation entry for retrieval
                citations_data.append({
                    "configuration": result.get("configuration", {}),
                    "chunks_with_answer": result.get("chunks_with_answer", 0),
                    "chunks_without_answer": result.get("chunks_without_answer", 0),
                    "chunk_quality": result.get("chunk_quality", 0),
                })
            
            test_run = TestRun(
                question_id=question.id,
                answer_text=result.get("actual_answer"),
                accuracy_score=result.get("accuracy_score"),
                response_time_ms=result.get("response_time_ms"),
                citations_json=citations_data if citations_data else None
            )
            db.add(test_run)
            db.commit()
        except Exception as e:
            logger.error(f"Error saving test run: {e}")
            db.rollback()
        finally:
            db.close()
    
    return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Run RAG test suite")
    parser.add_argument("--config", type=str, help="JSON configuration file")
    parser.add_argument("--strategy", choices=["single_query", "two_query"], help="RAG strategy")
    parser.add_argument("--bm25-weight", type=float, help="BM25 weight (0.0-1.0)")
    parser.add_argument("--vector-weight", type=float, help="Vector weight (0.0-1.0)")
    parser.add_argument("--rrf-k", type=int, help="RRF K parameter")
    parser.add_argument("--max-context-chunks", type=int, help="Max context chunks")
    parser.add_argument("--max-questions", type=int, help="Maximum number of questions to test")
    parser.add_argument("--question-ids", nargs="+", help="Specific question IDs to test")
    
    args = parser.parse_args()
    
    # Build configuration
    config = get_test_configuration()
    if args.config:
        with open(args.config, "r") as f:
            config.update(json.load(f))
    if args.strategy:
        config["rag_strategy"] = args.strategy
    if args.bm25_weight is not None:
        config["hybrid_bm25_weight"] = args.bm25_weight
    if args.vector_weight is not None:
        config["hybrid_vector_weight"] = args.vector_weight
    if args.rrf_k is not None:
        config["rrf_k"] = args.rrf_k
    if args.max_context_chunks is not None:
        config["max_context_chunks"] = args.max_context_chunks
    
    # Run tests
    results = asyncio.run(run_test_suite(
        config=config,
        question_ids=args.question_ids,
        max_questions=args.max_questions
    ))
    
    # Print summary
    total = len(results)
    passed = sum(1 for r in results if r.get("passed", False))
    avg_accuracy = sum(r.get("accuracy_score", 0) or 0 for r in results) / total if total > 0 else 0
    avg_chunk_quality = sum(r.get("chunk_quality", 0) for r in results) / total if total > 0 else 0
    avg_response_time = sum(r.get("response_time_ms", 0) for r in results) / total if total > 0 else 0
    
    print(f"\n{'='*80}")
    print("TEST SUITE SUMMARY")
    print(f"{'='*80}")
    print(f"Configuration: {json.dumps(config, indent=2)}")
    print(f"Total questions: {total}")
    print(f"Passed: {passed}/{total} ({100*passed/total:.1f}%)")
    
    # Phase 1: Metadata-first statistics
    metadata_answers = sum(1 for r in results if r.get("is_metadata_answer", False))
    if metadata_answers > 0:
        metadata_passed = sum(1 for r in results if r.get("is_metadata_answer", False) and r.get("passed", False))
        print(f"\nMetadata-First Answers: {metadata_answers} ({metadata_answers/total*100:.1f}%)")
        print(f"  Metadata Pass Rate: {metadata_passed}/{metadata_answers} ({metadata_passed/metadata_answers*100:.1f}%)")
    
    # Phase 5: Cross-document statistics
    cross_doc_queries = sum(1 for r in results if r.get("is_cross_document", False))
    if cross_doc_queries > 0:
        cross_doc_passed = sum(1 for r in results if r.get("is_cross_document", False) and r.get("passed", False))
        print(f"\nCross-Document Queries: {cross_doc_queries} ({cross_doc_queries/total*100:.1f}%)")
        print(f"  Cross-Doc Pass Rate: {cross_doc_passed}/{cross_doc_queries} ({cross_doc_passed/cross_doc_queries*100:.1f}%)")
    
    print(f"\nAverage accuracy: {avg_accuracy:.1%}")
    print(f"Average chunk quality: {avg_chunk_quality:.1%}")
    print(f"Average response time: {avg_response_time:.0f}ms")
    
    # Phase 7: 95%+ accuracy goal validation
    if avg_accuracy >= 0.95:
        print(f"\n✅ SUCCESS: Average accuracy ({avg_accuracy:.1%}) meets 95%+ goal!")
    elif avg_accuracy >= 0.80:
        print(f"\n⚠️  WARNING: Average accuracy ({avg_accuracy:.1%}) is below 95% goal but above 80%")
    else:
        print(f"\n❌ FAILURE: Average accuracy ({avg_accuracy:.1%}) is below 80%")
    
    print(f"{'='*80}")
    
    # Save results to JSON
    output_file = Path("reports") / f"rag_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w") as f:
        json.dump({
            "configuration": config,
            "summary": {
                "total": total,
                "passed": passed,
                "avg_accuracy": avg_accuracy,
                "avg_chunk_quality": avg_chunk_quality,
                "avg_response_time": avg_response_time,
            },
            "results": results
        }, f, indent=2)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()

