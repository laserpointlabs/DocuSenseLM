"""
Service bootstrap helpers.

Reads environment configuration and wires dependency overrides (e.g., in-memory
fakes for testing) via the service registry.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from api.services.service_registry import (
    override_storage_service,
    override_embedder_service,
    override_search_service,
    override_llm_service,
    override_bm25_indexer,
    override_vector_indexer,
    reset_storage_service,
    reset_embedder_service,
    reset_search_service,
    reset_llm_service,
    reset_bm25_indexer,
    reset_vector_indexer,
)
from api.services.fakes import (
    InMemoryStorageService,
    DeterministicEmbedder,
    InMemoryBM25Backend,
    InMemoryVectorBackend,
    InMemoryBM25Indexer,
    InMemoryVectorIndexer,
    EchoLLMClient,
)
from api.services.search_service import SearchService
from api.services.rerank import get_reranker

# Ensure default service implementations register their factories on import
import api.services.storage_service  # noqa: F401
import ingest.indexer_opensearch  # noqa: F401
import ingest.indexer_qdrant  # noqa: F401

_configured_state: Optional[Tuple[str, str]] = None


def configure_services_from_env(force: bool = False) -> None:
    """
    Configure service overrides based on SERVICE_PROFILE environment variable.

    Profiles:
        - "test" / "fake" / "local_fake": Use in-memory implementations for storage,
          embedding, search backends, and LLM.
        - Any other value: leave default (real) services in place.
    """
    global _configured_state

    profile = os.getenv("SERVICE_PROFILE", "").lower()
    rerank_strategy = os.getenv("RERANK_STRATEGY", "rrf").lower()
    state = (profile, rerank_strategy)

    if not force and _configured_state == state:
        return

    # Clear existing overrides when switching profiles
    if _configured_state is not None and (_configured_state != state or force):
        reset_vector_indexer()
        reset_bm25_indexer()
        reset_llm_service()
        reset_search_service()
        reset_embedder_service()
        reset_storage_service()

    if profile in {"test", "fake", "local_fake"}:
        storage = InMemoryStorageService()
        embedder = DeterministicEmbedder()
        bm25_backend = InMemoryBM25Backend()
        vector_backend = InMemoryVectorBackend()
        reranker = get_reranker(rerank_strategy)
        search = SearchService(
            bm25_backend=bm25_backend,
            vector_backend=vector_backend,
            embedder_provider=lambda: embedder,
            reranker=reranker,
        )
        llm = EchoLLMClient()
        bm25_indexer = InMemoryBM25Indexer(bm25_backend)
        vector_indexer = InMemoryVectorIndexer(vector_backend)

        override_storage_service(storage)
        override_embedder_service(embedder)
        override_search_service(search)
        override_llm_service(llm)
        override_bm25_indexer(bm25_indexer)
        override_vector_indexer(vector_indexer)

    _configured_state = state
