"""
OpenSearch indexing with BM25 and custom analyzers.

Implements the generic BM25Backend interface so the same object can be used for
indexing (ingestion pipeline) and querying (search service).
"""
from typing import Dict, List, Optional
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import bulk
import os

from api.services.search_backends.base import BM25Backend
from api.services.service_registry import register_bm25_indexer


class OpenSearchBM25Backend(BM25Backend):
    """OpenSearch-backed BM25 implementation."""

    def __init__(self):
        url = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
        username = os.getenv("OPENSEARCH_USER", "admin")
        password = os.getenv("OPENSEARCH_PASS", "admin123")

        self.client = OpenSearch(
            hosts=[url],
            http_auth=(username, password),
            use_ssl=False,
            verify_certs=False,
            connection_class=RequestsHttpConnection
        )
        self.index_name = "nda_documents"
        self._ensure_index()

    def _ensure_index(self):
        """Create index with custom analyzers if it doesn't exist"""
        if not self.client.indices.exists(index=self.index_name):
            index_body = {
                "settings": {
                    "analysis": {
                        "analyzer": {
                            "english_analyzer": {
                                "type": "standard",
                                "stopwords": "_english_"
                            },
                            "keyword_analyzer": {
                                "type": "keyword"
                            },
                            "nda_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": [
                                    "lowercase",
                                    "english_stemmer",
                                    "english_possessive_stemmer"
                                ]
                            }
                        },
                        "filter": {
                            "english_stemmer": {
                                "type": "stemmer",
                                "language": "english"
                            },
                            "english_possessive_stemmer": {
                                "type": "stemmer",
                                "language": "possessive_english"
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "doc_id": {"type": "keyword"},
                        "chunk_id": {"type": "keyword"},
                        "text": {
                            "type": "text",
                            "analyzer": "nda_analyzer",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "section_type": {"type": "keyword"},
                        "clause_number": {"type": "keyword"},
                        "page_num": {"type": "integer"},
                        "span_start": {"type": "integer"},
                        "span_end": {"type": "integer"},
                        "source_uri": {"type": "keyword"},
                        "parties": {"type": "keyword"},
                        "effective_date": {"type": "date"},
                        "governing_law": {"type": "keyword"},
                        "is_mutual": {"type": "boolean"},
                        "term_months": {"type": "integer"},
                        "survival_months": {"type": "integer"}
                    }
                }
            }

            self.client.indices.create(index=self.index_name, body=index_body)

    def index_chunks(self, chunks: List[Dict], document_metadata: Dict):
        """
        Index document chunks to OpenSearch
        Uses contextual text for better BM25 retrieval (Phase 3: Contextual Embeddings)

        Args:
            chunks: List of chunk dicts with text, metadata, etc.
            document_metadata: Document-level metadata (parties, dates, etc.)
        """
        actions = []

        for chunk in chunks:
            # Build contextual text for BM25 search (same as vector embeddings)
            contextual_text = self._build_contextual_text(chunk, document_metadata)
            
            action = {
                "_index": self.index_name,
                "_id": chunk.get("chunk_id", chunk.get("id")),
                "_source": {
                    "doc_id": chunk.get("document_id"),
                    "chunk_id": chunk.get("chunk_id", chunk.get("id")),
                    "text": chunk.get("text"),  # Original text
                    "contextual_text": contextual_text,  # Text with metadata for BM25 search
                    "section_type": chunk.get("section_type"),
                    "clause_number": chunk.get("clause_number"),
                    "page_num": chunk.get("page_num"),
                    "span_start": chunk.get("span_start"),
                    "span_end": chunk.get("span_end"),
                    "source_uri": chunk.get("source_uri"),
                    "parties": document_metadata.get("parties", []),
                    "effective_date": document_metadata.get("effective_date"),
                    "governing_law": document_metadata.get("governing_law"),
                    "is_mutual": document_metadata.get("is_mutual"),
                    "term_months": document_metadata.get("term_months"),
                    "survival_months": document_metadata.get("survival_months")
                }
            }
            actions.append(action)

        # Bulk index
        if actions:
            success, failed = bulk(self.client, actions, raise_on_error=False)
            if failed:
                print(f"Warning: {len(failed)} chunks failed to index")
            return success
        return 0
    
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

    def delete_document(self, document_id: str):
        """Delete all chunks for a document from OpenSearch"""
        try:
            # First verify documents exist
            search_result = self.client.search(
                index=self.index_name,
                body={
                    "query": {
                        "term": {"doc_id": document_id}
                    },
                    "size": 0  # We only need count
                }
            )

            total_hits = search_result["hits"]["total"]["value"]

            if total_hits > 0:
                # Delete all matching documents
                delete_result = self.client.delete_by_query(
                    index=self.index_name,
                    body={
                        "query": {
                            "term": {"doc_id": document_id}
                        }
                    },
                    refresh=True  # Refresh index immediately to make deletion visible
                )

                deleted_count = delete_result.get("deleted", 0)
                return deleted_count
            else:
                return 0
        except Exception as e:
            raise Exception(f"Failed to delete document {document_id} from OpenSearch: {e}")

    def search(self, query: str, k: int = 50, filters: Optional[Dict] = None) -> List[Dict]:
        """
        Search using BM25

        Args:
            query: Search query text
            k: Number of results to return
            filters: Optional filters (party, date_range, governing_law, is_mutual)

        Returns:
            List of search results
        """
        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "text": {
                                    "query": query,
                                    "analyzer": "nda_analyzer"
                                }
                            }
                        }
                    ]
                }
            },
            "size": k
        }

        # Add filters
        if filters:
            bool_query = search_body["query"]["bool"]
            if not bool_query.get("filter"):
                bool_query["filter"] = []

            if filters.get("party"):
                bool_query["filter"].append({
                    "term": {"parties": filters["party"]}
                })

            if filters.get("governing_law"):
                bool_query["filter"].append({
                    "term": {"governing_law": filters["governing_law"]}
                })

            if filters.get("is_mutual") is not None:
                bool_query["filter"].append({
                    "term": {"is_mutual": filters["is_mutual"]}
                })

            if filters.get("date_range"):
                date_range = filters["date_range"]
                bool_query["filter"].append({
                    "range": {
                        "effective_date": {
                            "gte": date_range.get("start"),
                            "lte": date_range.get("end")
                        }
                    }
                })

        response = self.client.search(index=self.index_name, body=search_body)

        results = []
        for hit in response["hits"]["hits"]:
            results.append({
                "chunk_id": hit["_id"],
                "score": hit["_score"],
                "text": hit["_source"]["text"],
                "doc_id": hit["_source"]["doc_id"],
                "section_type": hit["_source"]["section_type"],
                "clause_number": hit["_source"]["clause_number"],
                "clause_title": hit["_source"].get("clause_title"),  # Include clause_title for clause matching
                "page_num": hit["_source"]["page_num"],
                "span_start": hit["_source"]["span_start"],
                "span_end": hit["_source"]["span_end"],
                "source_uri": hit["_source"]["source_uri"]
            })

        return results


# Lazy singleton for legacy imports while avoiding connections during module import.
_singleton_backend: Optional[OpenSearchBM25Backend] = None


def _get_or_create_backend() -> OpenSearchBM25Backend:
    global _singleton_backend
    if _singleton_backend is None:
        _singleton_backend = OpenSearchBM25Backend()
    return _singleton_backend


class _LazyBackendProxy:
    def __getattr__(self, item: str):
        return getattr(_get_or_create_backend(), item)

    def __repr__(self) -> str:
        return "<OpenSearchBM25Backend (lazy proxy)>"


opensearch_backend = _LazyBackendProxy()
opensearch_indexer = opensearch_backend


def _bm25_indexer_factory() -> OpenSearchBM25Backend:
    return OpenSearchBM25Backend()


register_bm25_indexer(_bm25_indexer_factory)
