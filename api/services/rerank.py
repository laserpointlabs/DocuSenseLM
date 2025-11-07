"""Reranking utilities for hybrid search results."""
from __future__ import annotations

import os
from typing import Callable, Dict, List


def reciprocal_rank_fusion(
    bm25_results: List[Dict],
    vector_results: List[Dict],
    k: int = 10,
    base_results: List[Dict] | None = None,
    weight_bm25: float = 0.5,
    weight_vector: float = 0.5,
) -> List[Dict]:
    """Apply Reciprocal Rank Fusion to BM25 and vector rankings."""

    rrf_scores: Dict[str, float] = {}

    for weight, results in ((weight_bm25, bm25_results), (weight_vector, vector_results)):
        for rank, result in enumerate(results, 1):
            chunk_id = result.get("chunk_id")
            if not chunk_id:
                continue
            rrf_k = int(os.getenv("RRF_K", "60"))
            score = 1.0 / (rrf_k + rank)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + weight * score

    scored_results: List[Dict] = []
    seen = set()

    if base_results:
        for result in base_results:
            chunk_id = result.get("chunk_id")
            if not chunk_id:
                continue
            result = dict(result)
            result["score_rrf"] = rrf_scores.get(chunk_id, 0.0)
            scored_results.append(result)
            seen.add(chunk_id)

    for result in bm25_results + vector_results:
        chunk_id = result.get("chunk_id")
        if not chunk_id or chunk_id in seen:
            continue
        new_result = dict(result)
        new_result["score_rrf"] = rrf_scores.get(chunk_id, 0.0)
        scored_results.append(new_result)
        seen.add(chunk_id)

    scored_results.sort(key=lambda item: item.get("score_rrf", 0.0), reverse=True)

    if base_results is None:
        return scored_results[:k]

    merged = []
    for item in scored_results[:k]:
        merged.append(dict(item, score=item.get("score", 0.0)))
    return merged


def identity_reranker(
    _query: str,
    merged_results: List[Dict],
    _bm25_results: List[Dict],
    _vector_results: List[Dict],
) -> List[Dict]:
    """Return results unchanged."""

    return merged_results


def get_reranker(strategy: str | None) -> Callable[[str, List[Dict], List[Dict], List[Dict]], List[Dict]]:
    """Return reranker callable for a given strategy name."""

    if strategy is None:
        return identity_reranker

    strategy = strategy.lower()
    if strategy in {"none", "off"}:
        return identity_reranker
    if strategy in {"rrf", "reciprocal_rank_fusion"}:
        return lambda query, merged, bm25, vector: reciprocal_rank_fusion(
            bm25_results=bm25,
            vector_results=vector,
            k=len(merged),
            base_results=merged,
        )
    raise ValueError(f"Unknown reranker strategy: {strategy}")
