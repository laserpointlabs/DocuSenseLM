"""
Evaluation metrics for NDA question answering
"""
from typing import List, Dict, Optional
import time
import statistics


class EvaluationMetrics:
    """Calculate evaluation metrics"""

    @staticmethod
    def hit_rate_at_k(results: List[Dict], ground_truth: List[str], k: int = 10) -> float:
        """
        Calculate hit rate at K

        Args:
            results: List of result dicts with 'chunk_id' or 'doc_id'
            ground_truth: List of expected chunk/document IDs
            k: Top K results to consider

        Returns:
            Hit rate (0.0 to 1.0)
        """
        if not ground_truth:
            return 0.0

        top_k_ids = [r.get('chunk_id') or r.get('doc_id') for r in results[:k]]
        hits = sum(1 for gt_id in ground_truth if gt_id in top_k_ids)
        return hits / len(ground_truth)

    @staticmethod
    def mean_reciprocal_rank(results: List[Dict], ground_truth: List[str]) -> float:
        """
        Calculate Mean Reciprocal Rank (MRR)

        Args:
            results: List of result dicts
            ground_truth: List of expected IDs

        Returns:
            MRR score (0.0 to 1.0)
        """
        if not ground_truth:
            return 0.0

        for rank, result in enumerate(results, start=1):
            result_id = result.get('chunk_id') or result.get('doc_id')
            if result_id in ground_truth:
                return 1.0 / rank

        return 0.0

    @staticmethod
    def precision_at_k(results: List[Dict], ground_truth: List[str], k: int = 10) -> float:
        """
        Calculate precision at K

        Args:
            results: List of result dicts
            ground_truth: List of expected IDs
            k: Top K results to consider

        Returns:
            Precision (0.0 to 1.0)
        """
        if k == 0:
            return 0.0

        top_k_ids = [r.get('chunk_id') or r.get('doc_id') for r in results[:k]]
        true_positives = sum(1 for result_id in top_k_ids if result_id in ground_truth)
        return true_positives / k

    @staticmethod
    def recall_at_k(results: List[Dict], ground_truth: List[str], k: int = 10) -> float:
        """
        Calculate recall at K

        Args:
            results: List of result dicts
            ground_truth: List of expected IDs
            k: Top K results to consider

        Returns:
            Recall (0.0 to 1.0)
        """
        if not ground_truth:
            return 0.0

        top_k_ids = [r.get('chunk_id') or r.get('doc_id') for r in results[:k]]
        true_positives = sum(1 for gt_id in ground_truth if gt_id in top_k_ids)
        return true_positives / len(ground_truth)

    @staticmethod
    def calculate_latency_percentile(latencies: List[float], percentile: int = 95) -> float:
        """
        Calculate latency percentile

        Args:
            latencies: List of latency measurements in milliseconds
            percentile: Percentile to calculate (e.g., 95 for P95)

        Returns:
            Latency at specified percentile
        """
        if not latencies:
            return 0.0

        sorted_latencies = sorted(latencies)
        index = int(len(sorted_latencies) * (percentile / 100))
        if index >= len(sorted_latencies):
            index = len(sorted_latencies) - 1
        return sorted_latencies[index]

    @staticmethod
    def calculate_aggregate_metrics(
        all_results: List[Dict],
        ground_truth_mapping: Dict[str, List[str]]
    ) -> Dict:
        """
        Calculate aggregate metrics across all test cases

        Args:
            all_results: List of dicts with 'question_id', 'results', 'latency_ms'
            ground_truth_mapping: Dict mapping question_id to list of expected IDs

        Returns:
            Dictionary with aggregate metrics
        """
        hit_rates_k10 = []
        mrr_scores = []
        latencies = []
        precision_k10 = []
        recall_k10 = []

        for result in all_results:
            question_id = result['question_id']
            search_results = result['results']
            latency = result.get('latency_ms', 0)

            ground_truth = ground_truth_mapping.get(question_id, [])

            if ground_truth:
                hit_rates_k10.append(
                    EvaluationMetrics.hit_rate_at_k(search_results, ground_truth, k=10)
                )
                mrr_scores.append(
                    EvaluationMetrics.mean_reciprocal_rank(search_results, ground_truth)
                )
                precision_k10.append(
                    EvaluationMetrics.precision_at_k(search_results, ground_truth, k=10)
                )
                recall_k10.append(
                    EvaluationMetrics.recall_at_k(search_results, ground_truth, k=10)
                )

            if latency > 0:
                latencies.append(latency)

        aggregate = {
            'hit_rate_at_10': {
                'mean': statistics.mean(hit_rates_k10) if hit_rates_k10 else 0.0,
                'median': statistics.median(hit_rates_k10) if hit_rates_k10 else 0.0,
            },
            'mrr': {
                'mean': statistics.mean(mrr_scores) if mrr_scores else 0.0,
                'median': statistics.median(mrr_scores) if mrr_scores else 0.0,
            },
            'precision_at_10': {
                'mean': statistics.mean(precision_k10) if precision_k10 else 0.0,
                'median': statistics.median(precision_k10) if precision_k10 else 0.0,
            },
            'recall_at_10': {
                'mean': statistics.mean(recall_k10) if recall_k10 else 0.0,
                'median': statistics.median(recall_k10) if recall_k10 else 0.0,
            },
            'latency': {
                'p50': EvaluationMetrics.calculate_latency_percentile(latencies, 50) if latencies else 0.0,
                'p95': EvaluationMetrics.calculate_latency_percentile(latencies, 95) if latencies else 0.0,
                'p99': EvaluationMetrics.calculate_latency_percentile(latencies, 99) if latencies else 0.0,
                'mean': statistics.mean(latencies) if latencies else 0.0,
            },
            'total_questions': len(all_results),
            'questions_with_ground_truth': len([r for r in all_results if ground_truth_mapping.get(r['question_id'])]),
        }

        return aggregate
