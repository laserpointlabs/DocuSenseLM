#!/usr/bin/env python3
"""
Seed data: Load sample NDAs for testing
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingest.worker import worker
from api.services.bootstrap import configure_services_from_env
import api.services.storage_service  # Registers storage service with the registry
from api.services.service_registry import get_storage_service

# Ensure service registry is configured (needed for storage/search/etc.)
configure_services_from_env(force=True)
# Instantiate storage service upfront so ingestion has it cached
get_storage_service()


def seed_documents(docs_dir: str = "docs"):
    """
    Ingest all PDF/DOCX files from docs directory

    Args:
        docs_dir: Directory containing sample documents
    """
    docs_path = Path(docs_dir)

    if not docs_path.exists():
        print(f"Error: Directory '{docs_dir}' does not exist")
        return

    # Clean existing records
    from api.db import get_db_session
    from api.db.schema import Document, DocumentMetadata, DocumentChunk, Party

    db = get_db_session()
    try:
        deleted_chunks = db.query(DocumentChunk).delete()
        deleted_metadata = db.query(DocumentMetadata).delete()
        deleted_parties = db.query(Party).delete()
        deleted_documents = db.query(Document).delete()
        db.commit()
        print(
            "Cleared existing records: "
            f"documents={deleted_documents}, metadata={deleted_metadata}, "
            f"chunks={deleted_chunks}, parties={deleted_parties}"
        )
    finally:
        db.close()

    # Find all PDF and DOCX files
    pdf_files = list(docs_path.glob("*.pdf"))
    docx_files = list(docs_path.glob("*.docx"))
    all_files = pdf_files + docx_files

    if not all_files:
        print(f"No PDF or DOCX files found in '{docs_dir}'")
        return

    print(f"Found {len(all_files)} files to ingest")
    print(f"{'='*60}")

    success_count = 0
    error_count = 0

    for idx, file_path in enumerate(all_files, 1):
        print(f"\n[{idx}/{len(all_files)}] Processing: {file_path.name}")

        try:
            document_id = worker.ingest_document(str(file_path), file_path.name)
            print(f"  ✓ Ingested: {document_id}")
            success_count += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            error_count += 1

    print(f"\n{'='*60}")
    print(f"Seeding complete:")
    print(f"  Success: {success_count}")
    print(f"  Errors:  {error_count}")
    print(f"{'='*60}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Seed sample NDA documents')
    parser.add_argument(
        '--docs-dir',
        default='docs',
        help='Directory containing sample documents (default: docs)'
    )

    args = parser.parse_args()

    seed_documents(args.docs_dir)


if __name__ == '__main__':
    main()
