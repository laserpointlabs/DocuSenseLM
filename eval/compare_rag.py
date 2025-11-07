"""Compare retrieval metrics across reranker strategies."""
from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy

from api.services.bootstrap import configure_services_from_env
from eval.run_eval import load_qa_pairs, run_evaluation, print_metrics


def run_for_strategy(strategy: str, k: int, verbose: bool) -> dict:
    os.environ["RERANK_STRATEGY"] = strategy
    configure_services_from_env(force=True)

    qa_pairs = load_qa_pairs()
    results = run_evaluation(qa_pairs, k=k, verbose=verbose)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare RAG metrics across rerank strategies")
    parser.add_argument("strategies", nargs="*", default=["none", "rrf"], help="Strategies to evaluate")
    parser.add_argument("--k", type=int, default=50, help="Number of results per query")
    parser.add_argument("--verbose", action="store_true", help="Print detailed results per query")
    parser.add_argument("--output", type=str, help="Optional JSON file for metrics summary")

    args = parser.parse_args()

    summary = {}
    for strategy in args.strategies:
        print(f"\n=== Evaluating strategy: {strategy} ===")
        results = run_for_strategy(strategy, k=args.k, verbose=args.verbose)
        print_metrics(results)
        summary[strategy] = results["metrics"]

    if args.output:
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nSummary metrics written to {args.output}")


if __name__ == "__main__":
    main()
