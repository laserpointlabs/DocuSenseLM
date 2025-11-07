"""
Qdrant vector indexing + search backend implementation.
"""
from typing import Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
import os
import uuid

from api.services.service_registry import register_vector_indexer
from api.services.search_backends.base import VectorBackend


class QdrantVectorBackend(VectorBackend):
    """Qdrant-backed dense vector implementation."""

    def __init__(self):
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.client = QdrantClient(url=url)
        self.collection_name = "nda_documents"
        self.dimension = 768  # all-mpnet-base-v2 dimension
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            # Collection doesn't exist, create it
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.dimension,
                    distance=Distance.COSINE
                )
            )

    def index_chunks(
        self,
        chunks: List[Dict],
        embeddings: List[List[float]],
        metadata: Optional[Dict] = None,
    ):
        """
        Index document chunks with embeddings to Qdrant
        Uses contextual embeddings: prepends metadata to chunk text before embedding

        Args:
            chunks: List of chunk dicts
            embeddings: List of embedding vectors (768-dim) - should be generated from contextual text
            metadata: Optional document-level metadata
        """
        points = []

        metadata = metadata or {}

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = chunk.get("chunk_id", chunk.get("id"))
            
            # Build contextual text for this chunk (metadata context + original text)
            contextual_text = self._build_contextual_text(chunk, metadata)
            
            # Note: embeddings should already be generated from contextual_text
            # We store both original and contextual text for reference

            point = PointStruct(
                id=str(uuid.uuid4()) if not chunk_id else str(chunk_id),
                vector=embedding,
                payload={
                    "doc_id": chunk.get("document_id"),
                    "chunk_id": chunk_id,
                    "text": chunk.get("text"),  # Original text
                    "contextual_text": contextual_text,  # Text with metadata context
                    "section_type": chunk.get("section_type"),
                    "clause_number": chunk.get("clause_number"),
                    "page_num": chunk.get("page_num"),
                    "span_start": chunk.get("span_start"),
                    "span_end": chunk.get("span_end"),
                    "source_uri": chunk.get("source_uri"),
                    "parties": metadata.get("parties", []),
                    "effective_date": metadata.get("effective_date"),
                    "governing_law": metadata.get("governing_law"),
                    "is_mutual": metadata.get("is_mutual"),
                    "term_months": metadata.get("term_months"),
                    "survival_months": metadata.get("survival_months"),
                }
            )
            points.append(point)
    
    def _build_contextual_text(self, chunk: Dict, metadata: Dict) -> str:
        """
        Build contextual text by prepending metadata to chunk text
        
        Args:
            chunk: Chunk dict
            metadata: Document metadata
            
        Returns:
            Contextual text with metadata prefix
        """
        context_parts = []
        
        # Add document-level metadata context
        parties = metadata.get("parties", [])
        if parties:
            party_names = [p if isinstance(p, str) else p.get("name", "") for p in parties]
            party_str = ", ".join([p for p in party_names if p])
            if party_str:
                context_parts.append(f"Parties: {party_str}")
        
        governing_law = metadata.get("governing_law")
        if governing_law:
            context_parts.append(f"Governing Law: {governing_law}")
        
        effective_date = metadata.get("effective_date")
        if effective_date:
            if isinstance(effective_date, str):
                context_parts.append(f"Effective Date: {effective_date}")
            else:
                # Format datetime
                context_parts.append(f"Effective Date: {effective_date.strftime('%B %d, %Y')}")
        
        is_mutual = metadata.get("is_mutual")
        if is_mutual is not None:
            context_parts.append(f"Type: {'mutual' if is_mutual else 'unilateral'}")
        
        term_months = metadata.get("term_months")
        if term_months:
            if term_months >= 12:
                years = term_months // 12
                context_parts.append(f"Term: {years} {'year' if years == 1 else 'years'}")
            else:
                context_parts.append(f"Term: {term_months} {'month' if term_months == 1 else 'months'}")
        
        # Add clause title if available
        clause_title = chunk.get("clause_title")
        if clause_title:
            context_parts.append(f"Clause: {clause_title}")
        elif chunk.get("clause_number"):
            context_parts.append(f"Clause: {chunk.get('clause_number')}")
        
        # Build contextual text: metadata context + original text
        if context_parts:
            context_prefix = " | ".join(context_parts)
            return f"[{context_prefix}] {chunk.get('text', '')}"
        else:
            return chunk.get("text", "")

        # Batch upsert
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

    def delete_document(self, document_id: str):
        """Delete all chunks for a document from Qdrant"""
        try:
            # Use proper Filter model for deletion
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=document_id)
                    )
                ]
            )

            # First, verify points exist
            scroll_results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=filter_condition,
                limit=10000  # Get all points
            )

            points_to_delete = scroll_results[0]  # Results tuple: (points, next_page_offset)

            if points_to_delete:
                # Delete by point IDs (more reliable than filter-based delete)
                point_ids = [point.id for point in points_to_delete]
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=point_ids
                )
                return len(point_ids)
            else:
                return 0
        except Exception as e:
            # If scroll fails, try direct filter-based delete as fallback
            try:
                filter_condition = Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
                # Use filter-based delete (may not work in all Qdrant versions)
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=filter_condition
                )
                return -1  # Unknown count but attempted deletion
            except Exception as e2:
                raise Exception(f"Failed to delete document {document_id} from Qdrant: {e2}")

    def search(
        self,
        query_vector: List[float],
        k: int = 50,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Vector search

        Args:
            query_vector: Query embedding vector (768-dim)
            k: Number of results to return
            filters: Optional filters

        Returns:
            List of search results
        """
        # Build filter if provided
        query_filter: Optional[Filter] = None
        if filters:
            must_clauses: List[FieldCondition] = []

            if filters.get("party"):
                must_clauses.append(
                    FieldCondition(
                        key="parties",
                        match=MatchValue(value=filters["party"]),
                    )
                )

            if filters.get("governing_law"):
                must_clauses.append(
                    FieldCondition(
                        key="governing_law",
                        match=MatchValue(value=filters["governing_law"]),
                    )
                )

            if must_clauses:
                query_filter = Filter(must=must_clauses)

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=k,
            query_filter=query_filter
        )

        formatted_results = []
        for result in results:
            formatted_results.append({
                "chunk_id": result.payload.get("chunk_id"),
                "score": result.score,
                "text": result.payload.get("text"),
                "doc_id": result.payload.get("doc_id"),
                "section_type": result.payload.get("section_type"),
                "clause_number": result.payload.get("clause_number"),
                "clause_title": result.payload.get("clause_title"),  # Include clause_title for clause matching
                "page_num": result.payload.get("page_num"),
                "span_start": result.payload.get("span_start"),
                "span_end": result.payload.get("span_end"),
                "source_uri": result.payload.get("source_uri")
            })

        return formatted_results


# Lazy singleton for legacy imports (prevents connections during import time).
_singleton_backend: Optional[QdrantVectorBackend] = None


def _get_or_create_backend() -> QdrantVectorBackend:
    global _singleton_backend
    if _singleton_backend is None:
        _singleton_backend = QdrantVectorBackend()
    return _singleton_backend


class _LazyBackendProxy:
    def __getattr__(self, item: str):
        return getattr(_get_or_create_backend(), item)

    def __repr__(self) -> str:
        return "<QdrantVectorBackend (lazy proxy)>"


qdrant_backend = _LazyBackendProxy()
qdrant_indexer = qdrant_backend


def _vector_indexer_factory() -> QdrantVectorBackend:
    return QdrantVectorBackend()


register_vector_indexer(_vector_indexer_factory)
