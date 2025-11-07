from ingest.chunker import Chunker


def build_extracted_data():
    return {
        "title": "Mutual Non-Disclosure Agreement",
        "recitals": [
            {
                "text": "WHEREAS, the parties desire to explore a transaction.",
                "page_num": 1,
                "span_start": 0,
                "span_end": 64,
                "clause_number": "WHEREAS-1",
            }
        ],
        "clauses": [
            {
                "text": "1. Confidential Information. The parties shall keep all trade secrets confidential.",
                "clause_number": "1",
                "title": "Confidential Information",
                "page_num": 2,
                "span_start": 65,
                "span_end": 150,
            }
        ],
        "metadata": {
            "parties": [
                {"name": "Acme Inc.", "type": "disclosing", "address": "1 Main St"},
                {"name": "Beta LLC", "type": "receiving", "address": "2 Side Rd"},
            ]
        },
    }


def test_chunker_produces_expected_sections():
    extracted = build_extracted_data()
    chunker = Chunker()

    chunks = chunker.chunk_document(extracted, document_id="doc-123", source_uri="s3://bucket/doc.pdf")

    # Title, recital, parties, clause
    assert [chunk.section_type for chunk in chunks] == ["title", "recital", "parties", "clause"]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2, 3]

    title_chunk = chunks[0]
    assert title_chunk.text == extracted["title"]

    recital_chunk = chunks[1]
    assert recital_chunk.clause_number == "WHEREAS-1"

    parties_chunk = chunks[2]
    assert "Acme Inc." in parties_chunk.text and "Beta LLC" in parties_chunk.text

    clause_chunk = chunks[3]
    assert clause_chunk.clause_number == "1"
    assert clause_chunk.clause_title == "Confidential Information"
    assert clause_chunk.text.startswith("1. Confidential Information.")


def test_chunker_splits_large_clause():
    extracted = build_extracted_data()
    # Replace clauses with a very large clause to trigger splitting
    paragraph = "This paragraph contains detailed obligations regarding confidential information."
    large_text = "1. Confidential.\n\n" + "\n\n".join([paragraph] * 10)
    extracted["clauses"] = [
        {
            "text": large_text,
            "clause_number": "1",
            "title": "Confidential",
            "page_num": 2,
            "span_start": 0,
            "span_end": len(large_text),
        }
    ]

    chunker = Chunker()
    chunker.max_chunk_size = 150  # Force splitting
    chunker.min_chunk_size = 20

    chunks = chunker.chunk_document(extracted, document_id="doc-456", source_uri="s3://bucket/doc.pdf")

    # Title + recital + parties + several clause sub-chunks
    assert chunks[0].section_type == "title"
    clause_chunks = [chunk for chunk in chunks if chunk.section_type == "clause"]
    assert len(clause_chunks) > 1
    for clause_chunk in clause_chunks:
        assert len(clause_chunk.text) <= chunker.max_chunk_size
        assert clause_chunk.clause_number == "1"
