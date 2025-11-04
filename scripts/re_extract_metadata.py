#!/usr/bin/env python3
"""
Script to re-extract metadata (effective_date, term_months, governing_law) from documents
"""
import os
import sys
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import Document, DocumentMetadata, DocumentStatus
from ingest.clause_extractor import clause_extractor
from ingest.parser import DocumentParser
from api.services.storage_service import storage_service


def re_extract_metadata():
    """Re-extract metadata from all documents"""
    db = get_db_session()
    try:
        documents = db.query(Document).filter(
            Document.status == DocumentStatus.PROCESSED
        ).all()

        print(f"📋 Re-extracting metadata for {len(documents)} documents...")
        print()

        updated_count = 0

        for doc in documents:
            if not doc.s3_path:
                print(f"⚠️  Skipping {doc.filename[:50]:50} (no s3_path)")
                continue

            # Download file
            try:
                parts = doc.s3_path.split('/', 1) if '/' in doc.s3_path else ('nda-raw', f'{doc.id}/{doc.filename}')
                bucket = parts[0]
                object_name = parts[1]

                file_data = storage_service.download_file(bucket, object_name)

                # Save to temp file
                suffix = os.path.splitext(doc.filename)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(file_data)
                    temp_file = tmp.name

                # Parse and extract
                parser = DocumentParser()
                parsed = parser.parse(temp_file)
                full_text = parsed['text']

                # Extract metadata
                extracted_metadata = clause_extractor._extract_metadata(full_text)

                # Get or create metadata record
                metadata = db.query(DocumentMetadata).filter(
                    DocumentMetadata.document_id == doc.id
                ).first()

                if not metadata:
                    metadata = DocumentMetadata(document_id=doc.id)
                    db.add(metadata)

                # Update fields if extracted
                updates = []
                if extracted_metadata.get('effective_date') and not metadata.effective_date:
                    metadata.effective_date = extracted_metadata['effective_date']
                    updates.append(f"effective_date: {extracted_metadata['effective_date']}")

                if extracted_metadata.get('term_months') and not metadata.term_months:
                    metadata.term_months = extracted_metadata['term_months']
                    updates.append(f"term_months: {extracted_metadata['term_months']}")

                if extracted_metadata.get('governing_law'):
                    # Always update governing_law (clean it)
                    governing_law = clause_extractor._extract_governing_law(full_text)
                    if governing_law:
                        metadata.governing_law = governing_law
                        updates.append(f"governing_law: {governing_law}")

                if extracted_metadata.get('is_mutual') is not None and metadata.is_mutual is None:
                    metadata.is_mutual = extracted_metadata['is_mutual']
                    updates.append(f"is_mutual: {extracted_metadata['is_mutual']}")

                if extracted_metadata.get('survival_months') and not metadata.survival_months:
                    metadata.survival_months = extracted_metadata['survival_months']
                    updates.append(f"survival_months: {extracted_metadata['survival_months']}")

                if updates:
                    updated_count += 1
                    print(f"✅ {doc.filename[:50]:50}")
                    for update in updates:
                        print(f"   {update}")
                    print()

                os.unlink(temp_file)

            except Exception as e:
                print(f"❌ Error processing {doc.filename}: {e}")
                continue

        db.commit()
        print(f"✅ Updated metadata for {updated_count} documents")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 70)
    print("Re-extract Metadata from Documents")
    print("=" * 70)
    print()

    re_extract_metadata()

    print()
    print("=" * 70)
    print("Done!")
    print("=" * 70)
