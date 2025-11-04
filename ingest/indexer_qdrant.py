"""
Qdrant vector indexing
"""
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import os
import uuid


class QdrantIndexer:
    """Index vectors to Qdrant"""

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

    def index_chunks(self, chunks: List[Dict], embeddings: List[List[float]]):
        """
        Index document chunks with embeddings to Qdrant

        Args:
            chunks: List of chunk dicts
            embeddings: List of embedding vectors (768-dim)
        """
        points = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = chunk.get("chunk_id", chunk.get("id"))

            point = PointStruct(
                id=str(uuid.uuid4()) if not chunk_id else str(chunk_id),
                vector=embedding,
                payload={
                    "doc_id": chunk.get("document_id"),
                    "chunk_id": chunk_id,
                    "text": chunk.get("text"),
                    "section_type": chunk.get("section_type"),
                    "clause_number": chunk.get("clause_number"),
                    "page_num": chunk.get("page_num"),
                    "span_start": chunk.get("span_start"),
                    "span_end": chunk.get("span_end"),
                    "source_uri": chunk.get("source_uri")
                }
            )
            points.append(point)

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

    def search(self, query_vector: List[float], k: int = 50, filters: Dict = None) -> List[Dict]:
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
        query_filter = None
        if filters:
            must_clauses = []

            if filters.get("party"):
                must_clauses.append({
                    "key": "parties",
                    "match": {"value": filters["party"]}
                })

            if filters.get("governing_law"):
                must_clauses.append({
                    "key": "governing_law",
                    "match": {"value": filters["governing_law"]}
                })

            if must_clauses:
                query_filter = {"must": must_clauses}

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
                "page_num": result.payload.get("page_num"),
                "span_start": result.payload.get("span_start"),
                "span_end": result.payload.get("span_end"),
                "source_uri": result.payload.get("source_uri")
            })

        return formatted_results


# Global indexer instance
qdrant_indexer = QdrantIndexer()
