from api.services.rerank import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_prioritizes_results_in_both_lists():
    bm25_results = [
        {"chunk_id": "a", "score": 1.0},
        {"chunk_id": "b", "score": 0.8},
    ]
    vector_results = [
        {"chunk_id": "b", "score": 0.9},
        {"chunk_id": "c", "score": 0.7},
    ]

    reranked = reciprocal_rank_fusion(bm25_results, vector_results, k=3)
    chunk_ids = [res["chunk_id"] for res in reranked]
    assert chunk_ids[0] == "b"
    assert set(chunk_ids) == {"a", "b", "c"}
