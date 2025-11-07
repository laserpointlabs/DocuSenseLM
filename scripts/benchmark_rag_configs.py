#!/usr/bin/env python3
"""
Benchmark different RAG configurations systematically
Tests all combinations of configurations and generates comparison report
"""
import os
import sys
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.rag_test_suite import run_test_suite, get_test_configuration
from scripts.compare_test_runs import compare_configurations, find_best_configuration
from scripts.generate_test_report import generate_markdown_report, load_test_results_from_db


def generate_config_combinations() -> List[Dict]:
    """Generate all configuration combinations to test"""
    strategies = ["single_query", "two_query"]
    bm25_weights = [0.3, 0.4, 0.5, 0.6, 0.7]
    rrf_k_values = [40, 60, 80]
    max_context_chunks_values = [20, 30, 40]
    
    configs = []
    for strategy in strategies:
        for bm25_weight in bm25_weights:
            vector_weight = 1.0 - bm25_weight
            for rrf_k in rrf_k_values:
                for max_chunks in max_context_chunks_values:
                    configs.append({
                        "rag_strategy": strategy,
                        "hybrid_bm25_weight": bm25_weight,
                        "hybrid_vector_weight": vector_weight,
                        "rrf_k": rrf_k,
                        "max_context_chunks": max_chunks,
                        "context_window": int(os.getenv("OLLAMA_CONTEXT_LENGTH") or os.getenv("CONTEXT_WINDOW")),
                        "model": os.getenv("OLLAMA_MODEL") or os.getenv("LLM_MODEL"),
                    })
    
    return configs


async def benchmark_all_configs(
    configs: List[Dict],
    max_questions: Optional[int] = None,
    question_ids: Optional[List[str]] = None
) -> List[Dict]:
    """Run benchmark for all configurations"""
    all_results = []
    
    print(f"Benchmarking {len(configs)} configurations...")
    print("="*80)
    
    for i, config in enumerate(configs, 1):
        print(f"\n[{i}/{len(configs)}] Testing configuration:")
        print(f"  Strategy: {config['rag_strategy']}")
        print(f"  BM25 Weight: {config['hybrid_bm25_weight']}")
        print(f"  Vector Weight: {config['hybrid_vector_weight']}")
        print(f"  RRF K: {config['rrf_k']}")
        print(f"  Max Context Chunks: {config['max_context_chunks']}")
        
        try:
            results = await run_test_suite(
                config=config,
                question_ids=question_ids,
                max_questions=max_questions
            )
            all_results.extend(results)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    return all_results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark RAG configurations")
    parser.add_argument("--max-questions", type=int, help="Maximum questions per configuration")
    parser.add_argument("--question-ids", nargs="+", help="Specific question IDs to test")
    parser.add_argument("--configs", type=str, help="JSON file with specific configurations to test")
    parser.add_argument("--output-dir", type=str, default="reports", help="Output directory")
    
    args = parser.parse_args()
    
    # Get configurations to test
    if args.configs:
        with open(args.configs, "r") as f:
            configs = json.load(f)
            if not isinstance(configs, list):
                configs = [configs]
    else:
        configs = generate_config_combinations()
    
    print(f"Will test {len(configs)} configurations")
    if args.max_questions:
        print(f"Limited to {args.max_questions} questions per configuration")
    
    # Run benchmarks
    all_results = asyncio.run(benchmark_all_configs(
        configs=configs,
        max_questions=args.max_questions,
        question_ids=args.question_ids
    ))
    
    # Compare configurations
    config_metrics = compare_configurations(all_results)
    best_config = find_best_configuration(config_metrics)
    
    # Generate report
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = output_dir / f"rag_benchmark_report_{timestamp}.md"
    
    generate_markdown_report(all_results, report_file, include_graphs=True)
    
    # Save detailed results
    results_file = output_dir / f"rag_benchmark_results_{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump({
            "configurations_tested": len(configs),
            "total_test_runs": len(all_results),
            "config_metrics": config_metrics,
            "best_configuration": best_config,
            "all_results": all_results,
        }, f, indent=2)
    
    # Print summary
    print(f"\n{'='*80}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*80}")
    print(f"Configurations tested: {len(configs)}")
    print(f"Total test runs: {len(all_results)}")
    
    if best_config:
        print(f"\nBest Configuration:")
        print(f"  {best_config['configuration']}")
        print(f"  Pass Rate: {best_config['pass_rate']:.1%}")
        print(f"  Avg Accuracy: {best_config['avg_accuracy']:.1%}")
        print(f"  Avg Chunk Quality: {best_config['avg_chunk_quality']:.1%}")
        print(f"  Avg Response Time: {best_config['avg_response_time']:.0f}ms")
    
    print(f"\nReport: {report_file}")
    print(f"Results: {results_file}")


if __name__ == "__main__":
    main()

