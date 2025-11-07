#!/usr/bin/env python3
"""
Script to clean all documents from the database and storage
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import Document, DocumentChunk, Party, DocumentMetadata
from api.services.service_registry import get_storage_service

def clean_all_documents():
    """Delete all documents from database and storage"""
    db = get_db_session()
    try:
        # Get all documents
        documents = db.query(Document).all()
        print(f"Found {len(documents)} documents to delete")

        deleted_count = 0
        for doc in documents:
            print(f"Deleting: {doc.filename} (ID: {doc.id})")

            # Delete from storage if s3_path exists
            if doc.s3_path:
                try:
                    # Extract bucket and object name
                    if '/' in doc.s3_path:
                        parts = doc.s3_path.split('/', 1)
                        bucket = parts[0] if parts[0] else "nda-raw"
                        object_name = parts[1] if len(parts) > 1 else f"{doc.id}/{doc.filename}"
                    else:
                        bucket = "nda-raw"
                        object_name = f"{doc.id}/{doc.filename}"

                    # Try to delete from storage
                    try:
                        storage = get_storage_service()
                        storage.delete_file(bucket, object_name)
                        print(f"  - Deleted from storage: {bucket}/{object_name}")
                    except Exception as e:
                        print(f"  - Warning: Could not delete from storage: {e}")
                except Exception as e:
                    print(f"  - Warning: Could not parse s3_path: {e}")

            # Delete document (cascades to chunks, parties, metadata)
            db.delete(doc)
            deleted_count += 1

        db.commit()
        print(f"\n✅ Successfully deleted {deleted_count} documents")

        # Verify deletion
        remaining = db.query(Document).count()
        print(f"Remaining documents: {remaining}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("⚠️  WARNING: This will delete ALL documents from the database and storage!")
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() == 'yes':
        clean_all_documents()
    else:
        print("Cancelled.")
