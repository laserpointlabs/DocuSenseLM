#!/usr/bin/env python3
"""
Compare test runs across different configurations and over time
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import TestRun, CompetencyQuestion


def load_test_results_from_db(
    question_ids: Optional[List[str]] = None,
    limit: Optional[int] = None
) -> List[Dict]:
    """Load test results from database"""
    db = get_db_session()
    try:
        query = db.query(TestRun).order_by(TestRun.run_at.desc())
        
        if question_ids:
            query = query.filter(TestRun.question_id.in_(question_ids))
        
        if limit:
            query = query.limit(limit)
        
        runs = query.all()
        
        results = []
        for run in runs:
            question = db.query(CompetencyQuestion).filter(CompetencyQuestion.id == run.question_id).first()
            
            # Extract configuration from citations_json if available
            config = {}
            if run.citations_json and isinstance(run.citations_json, list) and len(run.citations_json) > 0:
                config = run.citations_json[0].get("configuration", {})
            
            results.append({
                "test_run_id": str(run.id),
                "question_id": str(run.question_id),
                "question_text": question.question_text if question else "Unknown",
                "expected_answer": question.expected_answer_text if question else None,
                "actual_answer": run.answer_text,
                "accuracy_score": run.accuracy_score,
                "response_time_ms": run.response_time_ms,
                "run_at": run.run_at.isoformat() if run.run_at else None,
                "configuration": config,
                "chunk_quality": run.citations_json[0].get("chunk_quality", 0) if run.citations_json and isinstance(run.citations_json, list) and len(run.citations_json) > 0 else 0,
            })
        
        return results
    finally:
        db.close()


def compare_configurations(results: List[Dict]) -> Dict:
    """Compare results across different configurations"""
    # Group by configuration
    config_groups = {}
    for result in results:
        config_key = json.dumps(result.get("configuration", {}), sort_keys=True)
        if config_key not in config_groups:
            config_groups[config_key] = []
        config_groups[config_key].append(result)
    
    # Calculate metrics for each configuration
    config_metrics = {}
    for config_key, config_results in config_groups.items():
        total = len(config_results)
        passed = sum(1 for r in config_results if r.get("accuracy_score", 0) >= 0.7)
        avg_accuracy = sum(r.get("accuracy_score", 0) or 0 for r in config_results) / total if total > 0 else 0
        avg_chunk_quality = sum(r.get("chunk_quality", 0) for r in config_results) / total if total > 0 else 0
        avg_response_time = sum(r.get("response_time_ms", 0) for r in config_results) / total if total > 0 else 0
        
        config_metrics[config_key] = {
            "configuration": json.loads(config_key),
            "total": total,
            "passed": passed,
            "pass_rate": passed / total if total > 0 else 0,
            "avg_accuracy": avg_accuracy,
            "avg_chunk_quality": avg_chunk_quality,
            "avg_response_time": avg_response_time,
        }
    
    return config_metrics


def find_best_configuration(config_metrics: Dict) -> Optional[Dict]:
    """Find best performing configuration"""
    if not config_metrics:
        return None
    
    # Score configurations: pass_rate * 0.5 + avg_accuracy * 0.3 + avg_chunk_quality * 0.2
    scored = []
    for config_key, metrics in config_metrics.items():
        score = (
            metrics["pass_rate"] * 0.5 +
            metrics["avg_accuracy"] * 0.3 +
            metrics["avg_chunk_quality"] * 0.2
        )
        scored.append((score, metrics))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else None


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare test runs")
    parser.add_argument("--question-ids", nargs="+", help="Specific question IDs to compare")
    parser.add_argument("--limit", type=int, help="Limit number of test runs to analyze")
    parser.add_argument("--output", type=str, help="Output JSON file")
    
    args = parser.parse_args()
    
    # Load results
    results = load_test_results_from_db(
        question_ids=args.question_ids,
        limit=args.limit
    )
    
    print(f"Loaded {len(results)} test runs")
    
    # Compare configurations
    config_metrics = compare_configurations(results)
    
    print(f"\n{'='*80}")
    print("CONFIGURATION COMPARISON")
    print(f"{'='*80}")
    
    for config_key, metrics in sorted(config_metrics.items(), key=lambda x: x[1]["pass_rate"], reverse=True):
        config = metrics["configuration"]
        print(f"\nConfiguration: {config}")
        print(f"  Total: {metrics['total']}")
        print(f"  Passed: {metrics['passed']} ({metrics['pass_rate']:.1%})")
        print(f"  Avg Accuracy: {metrics['avg_accuracy']:.1%}")
        print(f"  Avg Chunk Quality: {metrics['avg_chunk_quality']:.1%}")
        print(f"  Avg Response Time: {metrics['avg_response_time']:.0f}ms")
    
    # Find best
    best = find_best_configuration(config_metrics)
    if best:
        print(f"\n{'='*80}")
        print("BEST CONFIGURATION")
        print(f"{'='*80}")
        print(f"Configuration: {best['configuration']}")
        print(f"Pass Rate: {best['pass_rate']:.1%}")
        print(f"Avg Accuracy: {best['avg_accuracy']:.1%}")
        print(f"Avg Chunk Quality: {best['avg_chunk_quality']:.1%}")
        print(f"Avg Response Time: {best['avg_response_time']:.0f}ms")
    
    # Save to file
    if args.output:
        with open(args.output, "w") as f:
            json.dump({
                "configurations": config_metrics,
                "best_configuration": best,
                "total_runs": len(results),
            }, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()


