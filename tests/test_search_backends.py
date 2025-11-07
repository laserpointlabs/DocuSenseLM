from types import SimpleNamespace

from ingest.indexer_opensearch import OpenSearchBM25Backend
from ingest.indexer_qdrant import QdrantVectorBackend


def test_opensearch_backend_index_search_delete(monkeypatch):
    captured = {"bulk_actions": None, "search_calls": [], "delete_calls": []}

    class FakeIndices:
        def exists(self, index):
            return True

        def create(self, index, body):
            captured["created"] = (index, body)

    class FakeOpenSearch:
        def __init__(self, *args, **kwargs):
            self.indices = FakeIndices()

        def search(self, index, body):
            captured["search_calls"].append((index, body))
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "chunk-1",
                            "_score": 1.2,
                            "_source": {
                                "doc_id": "doc-1",
                                "text": "example",
                                "section_type": "clause",
                                "clause_number": "1",
                                "page_num": 1,
                                "span_start": 0,
                                "span_end": 10,
                                "source_uri": "s3://nda/doc-1.pdf",
                            },
                        }
                    ],
                    "total": {"value": 1},
                }
            }

        def delete_by_query(self, index, body, refresh):
            captured["delete_calls"].append((index, body, refresh))
            return {"deleted": 1}

    def fake_bulk(client, actions, raise_on_error=False):
        captured["bulk_actions"] = actions
        return len(actions), []

    monkeypatch.setattr("ingest.indexer_opensearch.OpenSearch", FakeOpenSearch)
    monkeypatch.setattr("ingest.indexer_opensearch.bulk", fake_bulk)

    backend = OpenSearchBM25Backend()
    chunks = [
        {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "text": "example",
            "section_type": "clause",
            "clause_number": "1",
            "page_num": 1,
            "span_start": 0,
            "span_end": 10,
            "source_uri": "s3://nda/doc-1.pdf",
        }
    ]
    metadata = {
        "parties": ["Acme"],
        "governing_law": "NY",
        "is_mutual": True,
        "term_months": 24,
        "survival_months": 12,
    }

    backend.index_chunks(chunks, metadata)
    assert captured["bulk_actions"] is not None
    assert captured["bulk_actions"][0]["_source"]["doc_id"] == "doc-1"

    results = backend.search("example", k=5, filters={"governing_law": "NY"})
    assert results[0]["doc_id"] == "doc-1"
    assert captured["search_calls"][0][1]["query"]["bool"]["filter"][0]["term"]["governing_law"] == "NY"

    deleted = backend.delete_document("doc-1")
    assert deleted == 1
    assert captured["delete_calls"][0][1]["query"]["term"]["doc_id"] == "doc-1"


def test_qdrant_backend_index_search_delete(monkeypatch):
    captured = {"points": [], "search_filter": None, "deleted": []}

    class FakeQdrantClient:
        def __init__(self, url=None):
            self.collections = set()

        def get_collection(self, collection_name):
            raise Exception("missing")

        def create_collection(self, collection_name, vectors_config):
            self.collections.add(collection_name)

        def upsert(self, collection_name, points):
            captured["points"].extend(points)

        def search(self, collection_name, query_vector, limit, query_filter=None):
            captured["search_filter"] = query_filter
            payload = captured["points"][0].payload if captured["points"] else {}
            return [SimpleNamespace(payload=payload, score=0.42)]

        def scroll(self, collection_name, scroll_filter=None, limit=10000):
            doc_id = scroll_filter.must[0].match.value
            points = [p for p in captured["points"] if p.payload.get("doc_id") == doc_id]
            return points, None

        def delete(self, collection_name, points_selector):
            ids = set(points_selector)
            captured["points"] = [p for p in captured["points"] if p.id not in ids]
            captured["deleted"].append(ids)

    monkeypatch.setattr("ingest.indexer_qdrant.QdrantClient", FakeQdrantClient)

    backend = QdrantVectorBackend()
    chunks = [
        {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "text": "example vector clause",
            "section_type": "clause",
            "clause_number": "2",
            "page_num": 3,
            "span_start": 0,
            "span_end": 21,
            "source_uri": "s3://nda/doc-1.pdf",
        }
    ]
    embeddings = [[0.1] * backend.dimension]
    metadata = {
        "parties": ["Acme"],
        "governing_law": "NY",
        "is_mutual": True,
        "term_months": 12,
        "survival_months": 12,
    }

    backend.index_chunks(chunks, embeddings, metadata)
    assert captured["points"]
    payload = captured["points"][0].payload
    assert payload["governing_law"] == "NY"
    assert payload["parties"] == ["Acme"]

    results = backend.search([0.1] * backend.dimension, k=5, filters={"party": "Acme"})
    assert results[0]["doc_id"] == "doc-1"
    assert captured["search_filter"].must[0].key == "parties"

    deleted = backend.delete_document("doc-1")
    assert deleted == 1
    assert not captured["points"]
