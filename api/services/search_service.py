"""
Search service for hybrid retrieval (BM25 + vector), now pluggable via service registry.
"""
from typing import Callable, List, Dict, Optional
import sys
import os

from api.services.service_registry import register_search_service, get_search_service
from api.services.rerank import get_reranker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from llm.llm_client import Chunk
except ImportError:
    Chunk = None


class SearchService:
    """Hybrid search service combining BM25 and vector search"""

    def __init__(
        self,
        bm25_backend,
        vector_backend,
        embedder_provider: Callable[[], object],
        reranker: Callable[[str, List[Dict], List[Dict], List[Dict]], List[Dict]] | None = None,
    ):
        self.bm25_backend = bm25_backend
        self.vector_backend = vector_backend
        self._embedder_provider = embedder_provider
        self._embedder = None
        self._reranker = reranker
        self._last_bm25_results = []
        self._last_vector_results = []

    def hybrid_search(
        self,
        query: str,
        k: int = 50,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Perform hybrid search (BM25 + vector)

        Args:
            query: Search query
            k: Number of results per method (returns up to k*2 total before merging)
            filters: Optional filters

        Returns:
            Merged and deduplicated results
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== Hybrid Search Start ===")
        logger.info(f"Query: {query}")
        logger.info(f"k: {k}, filters: {filters}")

        if self.bm25_backend is None or self.vector_backend is None:
            raise RuntimeError("Search backends are not configured")

        # BM25 search
        bm25_results = self.bm25_backend.search(query, k=k, filters=filters)
        logger.info(f"BM25 search returned {len(bm25_results)} results")
        if bm25_results:
            logger.info(f"Top BM25 result: doc_id={bm25_results[0].get('doc_id')[:8]}..., clause={bm25_results[0].get('clause_number')}, page={bm25_results[0].get('page_num')}, score={bm25_results[0].get('score'):.3f}")
            logger.info(f"  Text preview: {bm25_results[0].get('text', '')[:200]}")
        
        # Store for metrics tracking
        self._last_bm25_results = bm25_results

        # Vector search
        if self._embedder is None:
            self._embedder = self._embedder_provider()

        query_vector = self._embedder.embed_text(query)
        vector_results = self.vector_backend.search(query_vector, k=k, filters=filters)
        logger.info(f"Vector search returned {len(vector_results)} results")
        if vector_results:
            logger.info(f"Top vector result: doc_id={vector_results[0].get('doc_id')[:8]}..., clause={vector_results[0].get('clause_number')}, page={vector_results[0].get('page_num')}, score={vector_results[0].get('score'):.3f}")
            logger.info(f"  Text preview: {vector_results[0].get('text', '')[:200]}")
        
        # Store for metrics tracking
        self._last_vector_results = vector_results

        # Merge results
        merged = self._merge_results(bm25_results, vector_results, k)
        reranked = self._rerank_results(query, merged, bm25_results, vector_results)
        logger.info(f"Merged results: {len(merged)} total")
        if merged:
            logger.info(f"Top merged result: doc_id={merged[0].get('doc_id')[:8]}..., clause={merged[0].get('clause_number')}, page={merged[0].get('page_num')}, score={merged[0].get('score'):.3f}")
            logger.info(f"  Text preview: {merged[0].get('text', '')[:200]}")
        logger.info(f"=== Hybrid Search End ===")

        return reranked

    def _merge_results(
        self,
        bm25_results: List[Dict],
        vector_results: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """
        Merge BM25 and vector results with score normalization

        Args:
            bm25_results: BM25 search results
            vector_results: Vector search results
            top_k: Final number of results to return

        Returns:
            Merged, deduplicated, and sorted results
        """
        # Normalize scores to [0, 1] range
        bm25_scores = [r['score'] for r in bm25_results]
        vector_scores = [r['score'] for r in vector_results]

        bm25_max = max(bm25_scores) if bm25_scores else 1.0
        vector_max = max(vector_scores) if vector_scores else 1.0

        # Create score maps
        bm25_map = {}
        for result in bm25_results:
            chunk_id = result['chunk_id']
            normalized_score = result['score'] / bm25_max if bm25_max > 0 else 0
            bm25_map[chunk_id] = {
                **result,
                'bm25_score': normalized_score,
                'vector_score': 0.0
            }

        vector_map = {}
        for result in vector_results:
            chunk_id = result['chunk_id']
            normalized_score = result['score'] / vector_max if vector_max > 0 else 0
            vector_map[chunk_id] = {
                **result,
                'bm25_score': 0.0,
                'vector_score': normalized_score
            }

        # Merge: combine scores for chunks that appear in both
        merged_map = {}

        # Add BM25 results
        for chunk_id, result in bm25_map.items():
            merged_map[chunk_id] = result

        # Add/merge vector results
        for chunk_id, result in vector_map.items():
            if chunk_id in merged_map:
                # Combine scores (weighted average: configurable BM25 + vector weights)
                merged_map[chunk_id]['vector_score'] = result['vector_score']
                bm25_weight = float(os.getenv("HYBRID_BM25_WEIGHT", "0.5"))
                vector_weight = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.5"))
                merged_map[chunk_id]['score'] = (
                    bm25_weight * merged_map[chunk_id]['bm25_score'] +
                    vector_weight * result['vector_score']
                )
            else:
                merged_map[chunk_id] = result

        # Convert to list and sort by combined score
        merged_results = list(merged_map.values())
        merged_results.sort(key=lambda x: x['score'], reverse=True)

        # Return top k
        return merged_results[:top_k]

    def _rerank_results(
        self,
        query: str,
        merged_results: List[Dict],
        bm25_results: List[Dict],
        vector_results: List[Dict],
    ) -> List[Dict]:
        """Apply reranking while preserving merged metadata."""
        if not self._reranker:
            return merged_results

        import logging

        logger = logging.getLogger(__name__)

        try:
            reranked = self._reranker(query, merged_results, bm25_results, vector_results)
            return reranked or merged_results
        except Exception as exc:  # pragma: no cover
            logger.warning("Reranking failed for query '%s': %s", query, exc)
            return merged_results

    def get_chunks_for_answer(self, search_results: List[Dict]):
        """Convert search results to Chunk objects for LLM"""
        if Chunk is None:
            # Fallback if Chunk not imported
            return search_results

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== Converting {len(search_results)} search results to Chunk objects ===")

        chunks = []
        for i, result in enumerate(search_results):
            text = result.get('text', '')
            if not text or len(text.strip()) == 0:
                logger.warning(f"⚠️  Chunk {i+1} has empty or missing text! doc_id={result.get('doc_id')}, page={result.get('page_num')}")

            chunk = Chunk(
                text=text,
                doc_id=result.get('doc_id', ''),
                clause_number=result.get('clause_number'),
                page_num=result.get('page_num', 0),
                span_start=result.get('span_start', 0),
                span_end=result.get('span_end', 0),
                source_uri=result.get('source_uri', '')
            )
            chunks.append(chunk)
            logger.info(f"Chunk {i+1}: doc_id={chunk.doc_id[:8]}..., text_length={len(chunk.text)}, has_text={bool(chunk.text and chunk.text.strip())}")

        logger.info(f"Converted {len(chunks)} chunks, {sum(1 for c in chunks if c.text and c.text.strip())} have text")
        return chunks


def _default_search_factory() -> SearchService:
    from ingest.indexer_opensearch import opensearch_backend
    from ingest.indexer_qdrant import qdrant_backend
    from ingest.embedder import get_embedder
    from api.services.rerank import get_reranker

    strategy = os.getenv("RERANK_STRATEGY", "rrf")

    return SearchService(
        bm25_backend=opensearch_backend,
        vector_backend=qdrant_backend,
        embedder_provider=get_embedder,
        reranker=get_reranker(strategy),
    )


register_search_service(_default_search_factory)


def get_search_service_instance() -> SearchService:
    """Expose the registry-backed search service."""
    return get_search_service()
