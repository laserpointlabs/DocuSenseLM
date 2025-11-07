from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence
import math

from api.services.search_backends.base import BM25Backend, VectorBackend


@dataclass
class InMemoryDocument:
    chunk_id: str
    doc_id: str
    text: str
    metadata: Dict[str, Optional[str]] = field(default_factory=dict)
    vector: Optional[List[float]] = None


def _matches_filter(value: Optional[Sequence], expected) -> bool:
    if expected is None:
        return True
    if value is None:
        return False
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return expected in value
    return value == expected


class InMemoryBM25Backend(BM25Backend):
    """
    Minimal keyword-based backend for tests.
    Scores documents by simple term frequency.
    """

    def __init__(self):
        self.documents: Dict[str, InMemoryDocument] = {}

    def index_chunks(self, chunks: List[Dict], metadata: Dict) -> None:
        metadata = metadata or {}
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            if not chunk_id:
                continue
            combined_metadata = {
                **metadata,
                "section_type": chunk.get("section_type"),
                "clause_number": chunk.get("clause_number"),
                "page_num": chunk.get("page_num", 0),
                "span_start": chunk.get("span_start", 0),
                "span_end": chunk.get("span_end", 0),
                "source_uri": chunk.get("source_uri", ""),
            }
            document = InMemoryDocument(
                chunk_id=chunk_id,
                doc_id=chunk.get("document_id"),
                text=chunk.get("text", ""),
                metadata=combined_metadata,
            )
            self.documents[chunk_id] = document

    def clear(self) -> None:
        self.documents.clear()

    def delete_document(self, document_id: str) -> int:
        to_delete = [cid for cid, doc in self.documents.items() if doc.doc_id == document_id]
        for cid in to_delete:
            self.documents.pop(cid, None)
        return len(to_delete)

    def search(self, query: str, k: int = 50, filters: Optional[Dict] = None) -> List[Dict]:
        terms = [t.lower() for t in query.split() if t]
        results: List[Dict] = []
        for doc in self.documents.values():
            if not self._passes_filters(doc.metadata, filters):
                continue

            text_lower = doc.text.lower()
            tf = sum(text_lower.count(term) for term in terms)
            if tf == 0:
                continue
            result = {
                "chunk_id": doc.chunk_id,
                "doc_id": doc.doc_id,
                "text": doc.text,
                "section_type": doc.metadata.get("section_type"),
                "clause_number": doc.metadata.get("clause_number"),
                "page_num": doc.metadata.get("page_num", 0),
                "span_start": doc.metadata.get("span_start", 0),
                "span_end": doc.metadata.get("span_end", 0),
                "source_uri": doc.metadata.get("source_uri", ""),
                "score": float(tf),
            }
            results.append(result)
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:k]

    def _passes_filters(self, metadata: Dict, filters: Optional[Dict]) -> bool:
        if not filters:
            return True

        party = filters.get("party")
        governing_law = filters.get("governing_law")
        is_mutual = filters.get("is_mutual")

        if party and not _matches_filter(metadata.get("parties"), party):
            return False

        if governing_law and metadata.get("governing_law") != governing_law:
            return False

        if is_mutual is not None and metadata.get("is_mutual") is not None:
            if bool(metadata.get("is_mutual")) != bool(is_mutual):
                return False

        return True


class InMemoryVectorBackend(VectorBackend):
    """
    Minimal vector backend that performs cosine similarity against stored vectors.
    """

    def __init__(self):
        self.documents: Dict[str, InMemoryDocument] = {}

    def index_chunks(
        self,
        chunks: List[Dict],
        embeddings: List[List[float]],
        metadata: Optional[Dict] = None,
    ) -> None:
        metadata = metadata or {}

        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = chunk.get("chunk_id") or chunk.get("id")
            if not chunk_id:
                continue
            document = InMemoryDocument(
                chunk_id=chunk_id,
                doc_id=chunk.get("document_id"),
                text=chunk.get("text", ""),
                metadata={
                    **metadata,
                    "section_type": chunk.get("section_type"),
                    "clause_number": chunk.get("clause_number"),
                    "page_num": chunk.get("page_num", 0),
                    "span_start": chunk.get("span_start", 0),
                    "span_end": chunk.get("span_end", 0),
                    "source_uri": chunk.get("source_uri", ""),
                },
                vector=embedding,
            )
            self.documents[chunk_id] = document

    def clear(self) -> None:
        self.documents.clear()

    def delete_document(self, document_id: str) -> int:
        to_delete = [cid for cid, doc in self.documents.items() if doc.doc_id == document_id]
        for cid in to_delete:
            self.documents.pop(cid, None)
        return len(to_delete)

    def search(self, query_vector: List[float], k: int = 50, filters: Optional[Dict] = None) -> List[Dict]:
        def cosine(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            denom = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
            return dot / denom if denom else 0.0

        results: List[Dict] = []
        for doc in self.documents.values():
            if not self._passes_filters(doc.metadata, filters):
                continue

            sim = cosine(query_vector, doc.vector or [0.0])
            if sim <= 0:
                continue
            results.append({
                "chunk_id": doc.chunk_id,
                "doc_id": doc.doc_id,
                "text": doc.text,
                "section_type": doc.metadata.get("section_type"),
                "clause_number": doc.metadata.get("clause_number"),
                "page_num": doc.metadata.get("page_num", 0),
                "span_start": doc.metadata.get("span_start", 0),
                "span_end": doc.metadata.get("span_end", 0),
                "source_uri": doc.metadata.get("source_uri", ""),
                "score": float(sim),
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:k]

    def _passes_filters(self, metadata: Dict, filters: Optional[Dict]) -> bool:
        if not filters:
            return True

        party = filters.get("party")
        governing_law = filters.get("governing_law")
        is_mutual = filters.get("is_mutual")

        if party and not _matches_filter(metadata.get("parties"), party):
            return False

        if governing_law and metadata.get("governing_law") != governing_law:
            return False

        if is_mutual is not None and metadata.get("is_mutual") is not None:
            if bool(metadata.get("is_mutual")) != bool(is_mutual):
                return False

        return True
