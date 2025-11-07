from __future__ import annotations

from typing import Dict, List, Optional

from api.services.fakes.search import InMemoryBM25Backend, InMemoryVectorBackend


class InMemoryBM25Indexer:
    def __init__(self, backend: InMemoryBM25Backend):
        self.backend = backend

    def index_chunks(self, chunks: List[Dict], metadata: Optional[Dict]) -> None:
        self.backend.index_chunks(chunks, metadata or {})

    def delete_document(self, document_id: str) -> int:
        return self.backend.delete_document(document_id)


class InMemoryVectorIndexer:
    def __init__(self, backend: InMemoryVectorBackend):
        self.backend = backend

    def index_chunks(
        self,
        chunks: List[Dict],
        embeddings: List[List[float]],
        metadata: Optional[Dict] = None,
    ):
        self.backend.index_chunks(chunks, embeddings, metadata)

    def delete_document(self, document_id: str) -> int:
        return self.backend.delete_document(document_id)
