#!/usr/bin/env python3
"""
Re-index all documents
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.db import get_db_session
from api.db.schema import Document, DocumentChunk, DocumentStatus
from ingest.indexer_opensearch import opensearch_indexer
from ingest.indexer_qdrant import qdrant_indexer
from ingest.embedder import get_embedder


def reindex_document(document_id: str):
    """Re-index a single document"""
    db = next(get_db_session())
    try:
        # Get document
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            print(f"Document {document_id} not found")
            return False

        # Get chunks
        chunks = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).order_by(DocumentChunk.chunk_index).all()

        if not chunks:
            print(f"No chunks found for document {document_id}")
            return False

        print(f"Re-indexing {len(chunks)} chunks for document {doc.filename}...")

        # Get document metadata
        from api.services.db_service import db_service
        metadata = db_service.get_document_metadata(db, document_id)
        parties = db_service.get_parties(db, document_id)

        metadata_dict = {
            'parties': [p.party_name for p in parties],
            'effective_date': metadata.effective_date.isoformat() if metadata and metadata.effective_date else None,
            'governing_law': metadata.governing_law if metadata else None,
            'is_mutual': metadata.is_mutual if metadata else None,
            'term_months': metadata.term_months if metadata else None,
            'survival_months': metadata.survival_months if metadata else None,
        }

        # Prepare chunks
        chunk_dicts = []
        chunk_texts = []

        for chunk in chunks:
            chunk_dicts.append({
                'id': str(chunk.id),
                'chunk_id': str(chunk.id),
                'document_id': document_id,
                'text': chunk.text,
                'section_type': chunk.section_type,
                'clause_number': chunk.clause_number,
                'page_num': chunk.page_num,
                'span_start': chunk.span_start,
                'span_end': chunk.span_end,
                'source_uri': doc.s3_path or '',
            })
            chunk_texts.append(chunk.text)

        # Generate embeddings
        embedder = get_embedder()
        embeddings = embedder.embed_batch(chunk_texts)

        # Delete existing indices
        opensearch_indexer.delete_document(document_id)
        qdrant_indexer.delete_document(document_id)

        # Re-index
        opensearch_indexer.index_chunks(chunk_dicts, metadata_dict)
        qdrant_indexer.index_chunks(chunk_dicts, embeddings)

        print(f"✓ Re-indexed document {document_id}")
        return True

    finally:
        db.close()


def reindex_all():
    """Re-index all processed documents"""
    db = next(get_db_session())
    try:
        documents = db.query(Document).filter(
            Document.status == DocumentStatus.PROCESSED
        ).all()

        print(f"Found {len(documents)} documents to re-index")

        success_count = 0
        error_count = 0

        for idx, doc in enumerate(documents, 1):
            print(f"\n[{idx}/{len(documents)}] Processing: {doc.filename}")
            try:
                if reindex_document(str(doc.id)):
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                print(f"  ✗ Error: {e}")
                error_count += 1

        print(f"\n{'='*60}")
        print(f"Re-indexing complete:")
        print(f"  Success: {success_count}")
        print(f"  Errors:  {error_count}")
        print(f"{'='*60}")

    finally:
        db.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Re-index documents')
    parser.add_argument('--document-id', help='Re-index specific document ID')
    parser.add_argument('--all', action='store_true', help='Re-index all documents')

    args = parser.parse_args()

    if args.document_id:
        reindex_document(args.document_id)
    elif args.all:
        reindex_all()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
