#!/usr/bin/env python3
"""
Model Comparison Test Suite
Compares performance of multiple LLM models on RAG test questions
Tests: llama3.2:3b, mistral:7b, granite3.3:8b
Metrics: Correctness, Confidence, Speed
"""
import sys
import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from api.services.answer_service import answer_service
from api.services.answer_evaluator import answer_evaluator


# Model configurations to test
MODELS_TO_TEST = [
    {
        "name": "llama3.2:3b",
        "env_vars": {
            "OLLAMA_MODEL": "llama3.2:3b",
            "OLLAMA_CONTEXT_LENGTH": "8192",
            "LLM_PROVIDER": "ollama_local",
            "ENABLE_THINKING": "false"
        }
    },
    {
        "name": "mistral:7b",
        "env_vars": {
            "OLLAMA_MODEL": "mistral:7b",
            "OLLAMA_CONTEXT_LENGTH": "8192",
            "LLM_PROVIDER": "ollama_local",
            "ENABLE_THINKING": "false"
        }
    },
    {
        "name": "granite3.3:8b",
        "env_vars": {
            "OLLAMA_MODEL": "granite3.3:8b",
            "OLLAMA_CONTEXT_LENGTH": "32768",  # Granite supports 128K, but we'll use 32K for comparison
            "LLM_PROVIDER": "ollama_local",
            "ENABLE_THINKING": "false"
        }
    },
    {
        "name": "granite3.3:8b (thinking)",
        "env_vars": {
            "OLLAMA_MODEL": "granite3.3:8b",
            "OLLAMA_CONTEXT_LENGTH": "32768",
            "LLM_PROVIDER": "ollama_local",
            "ENABLE_THINKING": "true"
        }
    }
]


def load_test_questions() -> List[Dict[str, Any]]:
    """Load test questions from JSON file"""
    # Try multiple possible locations
    script_dir = Path(__file__).parent
    possible_locations = [
        script_dir.parent / 'document_specific_questions.json',
        Path('/app/document_specific_questions.json'),
        Path('/app/testing/rag/document_specific_questions.json'),
        Path(__file__).parent.parent.parent.parent / 'testing' / 'rag' / 'document_specific_questions.json'
    ]
    
    for questions_file in possible_locations:
        if questions_file.exists():
            print(f"Loading questions from: {questions_file}")
            with open(questions_file, 'r') as f:
                questions = json.load(f)
            return questions
    
    print(f"❌ Questions file not found in any of these locations:")
    for loc in possible_locations:
        print(f"   - {loc}")
    return []


def set_model_environment(model_config: Dict[str, str]):
    """Set environment variables for a specific model"""
    for key, value in model_config["env_vars"].items():
        os.environ[key] = value


async def run_test_with_model(
    model_config: Dict[str, Any],
    test_case: Dict[str, Any],
    test_num: int,
    total: int
) -> Dict[str, Any]:
    """Run a single test case with a specific model"""
    set_model_environment(model_config)
    
    # Clear any cached LLM clients to force reload with new model
    # Import here to avoid circular imports
    from api.services.answer_service import answer_service
    from api.services.answer_evaluator import answer_evaluator
    
    # Clear caches - force reload with new model
    answer_service.llm_client = None
    answer_evaluator.llm_client = None
    
    question = test_case['question']
    expected_contains = test_case.get('expected_contains', [])
    category = test_case.get('category', 'Other')
    
    print(f"[{model_config['name']}] [{test_num}/{total}] {category}: {question[:60]}...")
    
    start_time = time.time()
    
    try:
        # Generate answer
        answer_obj = await answer_service.generate_answer(question=question)
        generation_time = time.time() - start_time
        
        # Evaluate answer
        eval_start = time.time()
        expected_answer = test_case.get('expected_answer', '')
        expected_contains = test_case.get('expected_contains', [])
        
        # Build expected answer from contains if no explicit expected_answer
        if not expected_answer and expected_contains:
            expected_answer = ' '.join(expected_contains)
        
        if expected_answer:
            eval_result = await answer_evaluator.evaluate_answer(
                question=question,
                actual_answer=answer_obj.text,
                expected_answer=expected_answer,
                context_chunks=[
                    {
                        "text": c.excerpt or "",
                        "doc_id": c.doc_id,
                        "clause_number": c.clause_number,
                        "page_num": c.page_num
                    }
                    for c in answer_obj.citations
                ] if answer_obj.citations else None
            )
        else:
            eval_result = await answer_evaluator.evaluate_answer_quality(
                question=question,
                answer=answer_obj.text,
                context_chunks=[
                    {
                        "text": c.excerpt or "",
                        "doc_id": c.doc_id,
                        "clause_number": c.clause_number,
                        "page_num": c.page_num
                    }
                    for c in answer_obj.citations
                ] if answer_obj.citations else None
            )
        
        evaluation_time = time.time() - eval_start
        
        llm_confidence = eval_result.get("confidence", 0.0)
        llm_correctness = eval_result.get("correctness", False)
        
        # Check expected contains
        contains_match = False
        if expected_contains:
            answer_lower = answer_obj.text.lower()
            contains_match = any(
                exp.lower() in answer_lower for exp in expected_contains
            )
        
        # Determine pass/fail
        passed = llm_correctness or contains_match
        
        total_time = time.time() - start_time
        
        return {
            "model": model_config['name'],
            "question": question,
            "category": category,
            "expected_answer": expected_answer,
            "expected_contains": expected_contains,
            "actual_answer": answer_obj.text[:200],  # Truncate for storage
            "full_answer": answer_obj.text,
            "passed": passed,
            "llm_confidence": llm_confidence,
            "llm_correctness": llm_correctness,
            "contains_match": contains_match,
            "evaluation_reasoning": eval_result.get("reasoning", "")[:200],
            "generation_time_ms": int(generation_time * 1000),
            "evaluation_time_ms": int(evaluation_time * 1000),
            "total_time_ms": int(total_time * 1000),
            "citations_count": len(answer_obj.citations),
            "error": None
        }
        
    except Exception as e:
        total_time = time.time() - start_time
        return {
            "model": model_config['name'],
            "question": question,
            "category": category,
            "expected_answer": expected_answer,
            "expected_contains": expected_contains,
            "actual_answer": "",
            "full_answer": "",
            "passed": False,
            "llm_confidence": 0.0,
            "llm_correctness": False,
            "contains_match": False,
            "evaluation_reasoning": "",
            "generation_time_ms": int(total_time * 1000),
            "evaluation_time_ms": 0,
            "total_time_ms": int(total_time * 1000),
            "citations_count": 0,
            "error": str(e)
        }


async def run_model_comparison(
    models: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
    max_questions: Optional[int] = None
) -> Dict[str, Any]:
    """Run comparison tests across all models"""
    if max_questions:
        questions = questions[:max_questions]
    
    total_questions = len(questions)
    print(f"\n{'='*80}")
    print(f"Model Comparison Test Suite")
    print(f"{'='*80}")
    print(f"Models: {', '.join([m['name'] for m in models])}")
    print(f"Total Questions: {total_questions}")
    print(f"{'='*80}\n")
    
    all_results = []
    
    for model_config in models:
        print(f"\n{'='*80}")
        print(f"Testing Model: {model_config['name']}")
        print(f"{'='*80}\n")
        
        model_results = []
        
        for idx, test_case in enumerate(questions, 1):
            result = await run_test_with_model(
                model_config=model_config,
                test_case=test_case,
                test_num=idx,
                total=total_questions
            )
            model_results.append(result)
            
            # Print progress
            if idx % 10 == 0:
                passed = sum(1 for r in model_results if r['passed'])
                avg_time = sum(r['total_time_ms'] for r in model_results) / len(model_results)
                print(f"  Progress: {idx}/{total_questions} | Passed: {passed}/{idx} | Avg Time: {avg_time:.0f}ms")
        
        all_results.extend(model_results)
        
        # Print model summary
        passed = sum(1 for r in model_results if r['passed'])
        failed = len(model_results) - passed
        avg_confidence = sum(r['llm_confidence'] for r in model_results) / len(model_results) if model_results else 0
        avg_time = sum(r['total_time_ms'] for r in model_results) / len(model_results) if model_results else 0
        
        print(f"\n{model_config['name']} Summary:")
        print(f"  Passed: {passed}/{total_questions} ({passed/total_questions*100:.1f}%)")
        print(f"  Failed: {failed}/{total_questions}")
        print(f"  Avg Confidence: {avg_confidence:.3f}")
        print(f"  Avg Time: {avg_time:.0f}ms")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "models_tested": [m['name'] for m in models],
        "total_questions": total_questions,
        "results": all_results
    }


def generate_comparison_report(results: Dict[str, Any]) -> str:
    """Generate a markdown comparison report"""
    models = results['models_tested']
    total_questions = results['total_questions']
    all_results = results['results']
    
    # Organize results by model
    by_model = {}
    for model in models:
        model_results = [r for r in all_results if r['model'] == model]
        by_model[model] = model_results
    
    # Calculate statistics for each model
    stats = {}
    for model in models:
        model_results = by_model[model]
        passed = sum(1 for r in model_results if r['passed'])
        failed = len(model_results) - passed
        avg_confidence = sum(r['llm_confidence'] for r in model_results) / len(model_results) if model_results else 0
        avg_time = sum(r['total_time_ms'] for r in model_results) / len(model_results) if model_results else 0
        avg_gen_time = sum(r['generation_time_ms'] for r in model_results) / len(model_results) if model_results else 0
        avg_eval_time = sum(r['evaluation_time_ms'] for r in model_results) / len(model_results) if model_results else 0
        
        # Category breakdown
        by_category = {}
        for result in model_results:
            cat = result.get('category', 'Other')
            if cat not in by_category:
                by_category[cat] = {'total': 0, 'passed': 0}
            by_category[cat]['total'] += 1
            if result['passed']:
                by_category[cat]['passed'] += 1
        
        stats[model] = {
            'passed': passed,
            'failed': failed,
            'pass_rate': (passed / total_questions * 100) if total_questions > 0 else 0,
            'avg_confidence': avg_confidence,
            'avg_time_ms': avg_time,
            'avg_generation_time_ms': avg_gen_time,
            'avg_evaluation_time_ms': avg_eval_time,
            'by_category': by_category
        }
    
    # Generate report
    report = f"""# Model Comparison Test Report

**Generated:** {results['timestamp']}

## Executive Summary

| Model | Pass Rate | Avg Confidence | Avg Time (ms) | Avg Gen Time (ms) | Avg Eval Time (ms) |
|-------|-----------|----------------|---------------|-------------------|-------------------|"""
    
    # Sort by pass rate
    sorted_models = sorted(models, key=lambda m: stats[m]['pass_rate'], reverse=True)
    
    for model in sorted_models:
        s = stats[model]
        report += f"\n| **{model}** | {s['pass_rate']:.1f}% ({s['passed']}/{total_questions}) | {s['avg_confidence']:.3f} | {s['avg_time_ms']:.0f} | {s['avg_generation_time_ms']:.0f} | {s['avg_evaluation_time_ms']:.0f} |"
    
    report += f"""

## Detailed Performance Metrics

### Correctness Comparison

"""
    
    for model in sorted_models:
        s = stats[model]
        report += f"""
#### {model}
- **Pass Rate:** {s['pass_rate']:.1f}% ({s['passed']}/{total_questions})
- **Failed:** {s['failed']}/{total_questions}
- **Average Confidence:** {s['avg_confidence']:.3f}

**Category Breakdown:**
"""
        for category, cat_stats in sorted(s['by_category'].items()):
            cat_pass_rate = (cat_stats['passed'] / cat_stats['total'] * 100) if cat_stats['total'] > 0 else 0
            report += f"- {category}: {cat_pass_rate:.1f}% ({cat_stats['passed']}/{cat_stats['total']})\n"
    
    report += f"""

### Speed Comparison

| Model | Avg Total Time | Avg Generation | Avg Evaluation | Speed Rank |
|-------|----------------|----------------|----------------|------------|"""
    
    sorted_by_speed = sorted(models, key=lambda m: stats[m]['avg_time_ms'])
    for idx, model in enumerate(sorted_by_speed, 1):
        s = stats[model]
        report += f"\n| {model} | {s['avg_time_ms']:.0f}ms | {s['avg_generation_time_ms']:.0f}ms | {s['avg_evaluation_time_ms']:.0f}ms | #{idx} |"
    
    report += f"""

### Confidence Score Comparison

| Model | Avg Confidence | Confidence Rank |
|-------|----------------|-----------------|"""
    
    sorted_by_confidence = sorted(models, key=lambda m: stats[m]['avg_confidence'], reverse=True)
    for idx, model in enumerate(sorted_by_confidence, 1):
        s = stats[model]
        report += f"\n| {model} | {s['avg_confidence']:.3f} | #{idx} |"
    
    report += f"""

## Overall Rankings

### Best Overall Performance (Pass Rate + Confidence)
"""
    
    # Combined score: pass_rate * 0.6 + avg_confidence * 0.4 (normalized)
    combined_scores = {}
    max_pass_rate = max(s['pass_rate'] for s in stats.values())
    max_confidence = max(s['avg_confidence'] for s in stats.values())
    
    for model in models:
        s = stats[model]
        normalized_pass = (s['pass_rate'] / max_pass_rate) if max_pass_rate > 0 else 0
        normalized_conf = (s['avg_confidence'] / max_confidence) if max_confidence > 0 else 0
        combined_score = normalized_pass * 0.6 + normalized_conf * 0.4
        combined_scores[model] = combined_score
    
    sorted_by_combined = sorted(models, key=lambda m: combined_scores[m], reverse=True)
    for idx, model in enumerate(sorted_by_combined, 1):
        score = combined_scores[model]
        report += f"{idx}. **{model}** (Score: {score:.3f})\n"
    
    report += f"""

### Fastest Model
1. **{sorted_by_speed[0]}** ({stats[sorted_by_speed[0]]['avg_time_ms']:.0f}ms avg)

### Highest Confidence
1. **{sorted_by_confidence[0]}** ({stats[sorted_by_confidence[0]]['avg_confidence']:.3f} avg)

## Recommendations

"""
    
    best_overall = sorted_by_combined[0]
    fastest = sorted_by_speed[0]
    most_confident = sorted_by_confidence[0]
    
    report += f"""
- **Best Overall:** {best_overall} - Best balance of correctness and confidence
- **Fastest:** {fastest} - Best for low-latency applications
- **Most Confident:** {most_confident} - Best for high-confidence requirements

### Model-Specific Notes

"""
    
    # Add notes about Granite thinking feature
    if 'granite3.3:8b' in models:
        report += """
#### Granite 3.3:8b
- Supports 128K context window (tested with 32K for comparison)
- Has "thinking" mode capability for improved reasoning
- Optimized for RAG and instruction-following tasks
- See: https://ollama.com/library/granite3.3

"""
    
    report += f"""
## Test Configuration

- **Total Questions:** {total_questions}
- **Models Tested:** {', '.join(models)}
- **Evaluation Method:** LLM-based semantic evaluation
- **Context Length:** 8K-32K (model-dependent)

## Raw Results

Full detailed results are available in the JSON output file.

---
*Report generated by Model Comparison Test Suite*
"""
    
    return report


async def main():
    """Main execution"""
    # Load test questions
    questions = load_test_questions()
    
    if not questions:
        print("❌ No test questions found. Exiting.")
        return
    
    print(f"Loaded {len(questions)} test questions")
    
    # Option to limit questions for faster testing
    import sys
    max_questions = None
    if len(sys.argv) > 1:
        try:
            max_questions = int(sys.argv[1])
            print(f"Limiting to first {max_questions} questions")
        except ValueError:
            pass
    
    # Run comparison
    results = await run_model_comparison(
        models=MODELS_TO_TEST,
        questions=questions,
        max_questions=max_questions
    )
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path('/app/testing/rag/results')
    results_dir.mkdir(parents=True, exist_ok=True)
    
    json_file = results_dir / f'model_comparison_{timestamp}.json'
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Results saved to: {json_file}")
    
    # Generate report
    report = generate_comparison_report(results)
    report_file = results_dir / f'model_comparison_report_{timestamp}.md'
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"✅ Report saved to: {report_file}")
    
    # Print summary
    print("\n" + "="*80)
    print("COMPARISON SUMMARY")
    print("="*80)
    
    models = results['models_tested']
    all_results = results['results']
    
    for model in models:
        model_results = [r for r in all_results if r['model'] == model]
        passed = sum(1 for r in model_results if r['passed'])
        avg_conf = sum(r['llm_confidence'] for r in model_results) / len(model_results) if model_results else 0
        avg_time = sum(r['total_time_ms'] for r in model_results) / len(model_results) if model_results else 0
        
        print(f"\n{model}:")
        print(f"  Pass Rate: {passed}/{len(model_results)} ({passed/len(model_results)*100:.1f}%)")
        print(f"  Avg Confidence: {avg_conf:.3f}")
        print(f"  Avg Time: {avg_time:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())

