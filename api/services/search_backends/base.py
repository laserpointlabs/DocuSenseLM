from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BM25Backend(ABC):
    @abstractmethod
    def search(self, query: str, k: int = 50, filters: Optional[Dict] = None) -> List[Dict]:
        raise NotImplementedError

    @abstractmethod
    def index_chunks(self, chunks: List[Dict], metadata: Dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, document_id: str) -> int:
        raise NotImplementedError


class VectorBackend(ABC):
    @abstractmethod
    def search(self, query_vector: List[float], k: int = 50, filters: Optional[Dict] = None) -> List[Dict]:
        raise NotImplementedError

    @abstractmethod
    def index_chunks(
        self,
        chunks: List[Dict],
        embeddings: List[List[float]],
        metadata: Optional[Dict] = None
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, document_id: str) -> int:
        raise NotImplementedError
