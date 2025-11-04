"""
OpenSearch indexing with BM25 and custom analyzers
"""
from typing import List, Dict
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import bulk
import os
import json


class OpenSearchIndexer:
    """Index documents to OpenSearch for BM25 search"""

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

        Args:
            chunks: List of chunk dicts with text, metadata, etc.
            document_metadata: Document-level metadata (parties, dates, etc.)
        """
        actions = []

        for chunk in chunks:
            action = {
                "_index": self.index_name,
                "_id": chunk.get("chunk_id", chunk.get("id")),
                "_source": {
                    "doc_id": chunk.get("document_id"),
                    "chunk_id": chunk.get("chunk_id", chunk.get("id")),
                    "text": chunk.get("text"),
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

    def search(self, query: str, k: int = 50, filters: Dict = None) -> List[Dict]:
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
                "page_num": hit["_source"]["page_num"],
                "span_start": hit["_source"]["span_start"],
                "span_end": hit["_source"]["span_end"],
                "source_uri": hit["_source"]["source_uri"]
            })

        return results


# Global indexer instance
opensearch_indexer = OpenSearchIndexer()
