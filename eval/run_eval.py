#!/usr/bin/env python3
"""
Evaluation harness CLI
Runs QA pairs against the system and calculates metrics
"""
import os
import sys
import json
import time
import argparse
from typing import List, Dict
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.search_service import search_service
from eval.metrics import EvaluationMetrics

# Load QA pairs
QA_PAIRS_FILE = Path(__file__).parent / "qa_pairs.json"


def load_qa_pairs() -> List[Dict]:
    """Load QA pairs from JSON file"""
    with open(QA_PAIRS_FILE, 'r') as f:
        return json.load(f)


def run_evaluation(
    qa_pairs: List[Dict],
    k: int = 50,
    verbose: bool = False
) -> Dict:
    """
    Run evaluation on QA pairs

    Args:
        qa_pairs: List of QA pair dicts
        k: Number of results to retrieve per query
        verbose: Print detailed results

    Returns:
        Dictionary with evaluation results
    """
    all_results = []
    ground_truth_mapping = {}

    print(f"Running evaluation on {len(qa_pairs)} QA pairs...")
    print("-" * 60)

    for idx, qa_pair in enumerate(qa_pairs, 1):
        question_id = qa_pair.get('id', f'qa_{idx}')
        question = qa_pair['question']
        expected_keywords = qa_pair.get('expected_clause_keywords', [])

        if verbose:
            print(f"\n[{idx}/{len(qa_pairs)}] Question: {question}")

        # Run search
        start_time = time.time()
        try:
            results = search_service.hybrid_search(query=question, k=k)
            latency_ms = (time.time() - start_time) * 1000
        except Exception as e:
            print(f"Error processing question {question_id}: {e}")
            results = []
            latency_ms = 0

        # Store results
        result_entry = {
            'question_id': question_id,
            'question': question,
            'results': results,
            'latency_ms': latency_ms,
            'num_results': len(results)
        }
        all_results.append(result_entry)

        # For now, we don't have explicit ground truth IDs
        # We'll use keyword matching as a proxy
        # In production, you'd have actual chunk/document IDs
        ground_truth = []  # TODO: Map to actual chunk IDs

        if expected_keywords:
            # Find results that contain expected keywords
            for result in results:
                text_lower = result.get('text', '').lower()
                if any(keyword.lower() in text_lower for keyword in expected_keywords):
                    ground_truth.append(result.get('chunk_id', ''))

        ground_truth_mapping[question_id] = ground_truth

        if verbose:
            print(f"  Results: {len(results)}, Latency: {latency_ms:.2f}ms")
            if ground_truth:
                print(f"  Ground truth matches: {len(ground_truth)}")

    # Calculate metrics
    print("\n" + "=" * 60)
    print("Calculating metrics...")

    metrics = EvaluationMetrics.calculate_aggregate_metrics(
        all_results,
        ground_truth_mapping
    )

    return {
        'metrics': metrics,
        'results': all_results,
        'ground_truth_mapping': ground_truth_mapping
    }


def print_metrics(metrics: Dict):
    """Print metrics in a readable format"""
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    m = metrics['metrics']

    print(f"\nHit Rate @ 10:")
    print(f"  Mean:   {m['hit_rate_at_10']['mean']:.3f}")
    print(f"  Median: {m['hit_rate_at_10']['median']:.3f}")

    print(f"\nMean Reciprocal Rank (MRR):")
    print(f"  Mean:   {m['mrr']['mean']:.3f}")
    print(f"  Median: {m['mrr']['median']:.3f}")

    print(f"\nPrecision @ 10:")
    print(f"  Mean:   {m['precision_at_10']['mean']:.3f}")
    print(f"  Median: {m['precision_at_10']['median']:.3f}")

    print(f"\nRecall @ 10:")
    print(f"  Mean:   {m['recall_at_10']['mean']:.3f}")
    print(f"  Median: {m['recall_at_10']['median']:.3f}")

    print(f"\nLatency (ms):")
    print(f"  Mean:   {m['latency']['mean']:.2f}")
    print(f"  P50:    {m['latency']['p50']:.2f}")
    print(f"  P95:    {m['latency']['p95']:.2f}")
    print(f"  P99:    {m['latency']['p99']:.2f}")

    print(f"\nTotal Questions: {m['total_questions']}")
    print(f"Questions with Ground Truth: {m['questions_with_ground_truth']}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Run NDA Dashboard evaluation')
    parser.add_argument(
        '--k',
        type=int,
        default=50,
        help='Number of results to retrieve per query (default: 50)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed results for each question'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file for detailed results (JSON format)'
    )

    args = parser.parse_args()

    # Load QA pairs
    qa_pairs = load_qa_pairs()

    # Run evaluation
    results = run_evaluation(qa_pairs, k=args.k, verbose=args.verbose)

    # Print metrics
    print_metrics(results)

    # Save results if output file specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nDetailed results saved to: {args.output}")


if __name__ == '__main__':
    main()
