def test_hybrid_search_returns_keyword_and_vector_matches(fake_service_registry):
    env = fake_service_registry
    embedder = env["embedder"]
    bm25 = env["bm25"]
    vector = env["vector"]
    search = env["search"]

    chunk = {
        "chunk_id": "chunk-1",
        "document_id": "doc-1",
        "text": "The confidential information includes sensitive trade secrets.",
        "section_type": "clause",
        "clause_number": "1",
        "page_num": 2,
        "span_start": 0,
        "span_end": 64,
        "source_uri": "s3://nda/doc-1.pdf",
    }
    metadata = {
        "parties": ["Acme"],
        "governing_law": "NY",
        "is_mutual": True,
    }

    bm25.index_chunks([chunk], metadata)
    vector.index_chunks([chunk], [embedder.embed_text(chunk["text"])], metadata)

    results = search.hybrid_search("confidential trade", k=5)
    assert len(results) == 1
    result = results[0]
    assert result["doc_id"] == "doc-1"
    assert result["section_type"] == "clause"
    assert result["score"] > 0
    assert result.get("score_rrf") is not None


def test_hybrid_search_merges_scores_from_both_backends(fake_service_registry):
    env = fake_service_registry
    embedder = env["embedder"]
    bm25 = env["bm25"]
    vector = env["vector"]
    search = env["search"]

    bm25_chunk = {
        "chunk_id": "bm25-only",
        "document_id": "doc-2",
        "text": "Confidential information must be returned within ten days.",
        "section_type": "clause",
        "page_num": 1,
    }
    vector_chunk = {
        "chunk_id": "vector-only",
        "document_id": "doc-3",
        "text": "Sensitive data should be handled carefully.",
        "section_type": "clause",
        "page_num": 3,
    }
    metadata = {"parties": ["Acme"], "governing_law": "CA", "is_mutual": False}

    bm25.index_chunks([bm25_chunk], metadata)
    vector.index_chunks([vector_chunk], [embedder.embed_text(vector_chunk["text"])], metadata)

    results = search.hybrid_search("sensitive confidential", k=10)
    chunk_ids = [r["chunk_id"] for r in results]
    assert {"bm25-only", "vector-only"}.issubset(chunk_ids)
    assert chunk_ids[0] in {"bm25-only", "vector-only"}
    assert results[0].get("score_rrf") is not None
