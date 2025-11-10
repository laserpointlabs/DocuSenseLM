#!/usr/bin/env python3
"""
Comprehensive script to clean ALL data from the system:
- Database records (documents, chunks, metadata, parties, nda_records, etc.)
- MinIO storage (nda-raw and nda-processed buckets)
- OpenSearch indices
- Qdrant collections

NOTE: This script does NOT delete PDF files from the data/ directory.
      PDF files are preserved so they can be reloaded after cleanup.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import (
    Document, DocumentChunk, Party, DocumentMetadata,
    CompetencyQuestion, QuestionGroundTruth, TestRun, TestFeedback,
    NDARecord, NDAEvent
)
from api.services.service_registry import get_storage_service
from api.services.storage_service import StorageService
from ingest.indexer_opensearch import opensearch_indexer
from ingest.indexer_qdrant import qdrant_indexer
from qdrant_client.models import Filter, FieldCondition, MatchValue


def clean_local_pdfs(data_dir: str = "data"):
    """Delete all PDF files from the local data directory"""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"⚠️  Data directory {data_dir} does not exist, skipping...")
        return 0
    
    pdf_files = list(data_path.glob("*.pdf"))
    docx_files = list(data_path.glob("*.docx"))
    all_files = pdf_files + docx_files
    
    if not all_files:
        print(f"✓ No files found in {data_dir}/")
        return 0
    
    deleted_count = 0
    for file_path in all_files:
        try:
            file_path.unlink()
            print(f"  - Deleted: {file_path.name}")
            deleted_count += 1
        except Exception as e:
            print(f"  - Warning: Could not delete {file_path.name}: {e}")
    
    print(f"✓ Deleted {deleted_count} files from {data_dir}/")
    return deleted_count


def clean_database():
    """Delete all data from the database"""
    db = get_db_session()
    try:
        print("\n📊 Cleaning database...")
        
        # Get counts before deletion
        doc_count = db.query(Document).count()
        chunk_count = db.query(DocumentChunk).count()
        party_count = db.query(Party).count()
        metadata_count = db.query(DocumentMetadata).count()
        nda_record_count = db.query(NDARecord).count()
        nda_event_count = db.query(NDAEvent).count()
        question_count = db.query(CompetencyQuestion).count()
        test_run_count = db.query(TestRun).count()
        test_feedback_count = db.query(TestFeedback).count()
        ground_truth_count = db.query(QuestionGroundTruth).count()
        
        print(f"  Found: {doc_count} documents, {chunk_count} chunks, {party_count} parties, "
              f"{metadata_count} metadata records, {nda_record_count} NDA records, "
              f"{nda_event_count} NDA events, {question_count} questions, "
              f"{test_run_count} test runs, {test_feedback_count} test feedback, "
              f"{ground_truth_count} ground truth records")
        
        # Delete in order to respect foreign key constraints
        deleted_feedback = db.query(TestFeedback).delete()
        deleted_runs = db.query(TestRun).delete()
        deleted_ground_truth = db.query(QuestionGroundTruth).delete()
        deleted_questions = db.query(CompetencyQuestion).delete()
        deleted_events = db.query(NDAEvent).delete()
        deleted_nda_records = db.query(NDARecord).delete()
        deleted_chunks = db.query(DocumentChunk).delete()
        deleted_metadata = db.query(DocumentMetadata).delete()
        deleted_parties = db.query(Party).delete()
        deleted_documents = db.query(Document).delete()
        
        db.commit()
        
        print(f"✓ Deleted from database:")
        print(f"    - {deleted_documents} documents")
        print(f"    - {deleted_chunks} chunks")
        print(f"    - {deleted_parties} parties")
        print(f"    - {deleted_metadata} metadata records")
        print(f"    - {deleted_nda_records} NDA records")
        print(f"    - {deleted_events} NDA events")
        print(f"    - {deleted_questions} questions")
        print(f"    - {deleted_runs} test runs")
        print(f"    - {deleted_feedback} test feedback")
        print(f"    - {deleted_ground_truth} ground truth records")
        
        return deleted_documents
    except Exception as e:
        db.rollback()
        print(f"❌ Error cleaning database: {e}")
        raise
    finally:
        db.close()


def clean_minio_storage():
    """Delete all files from MinIO storage buckets"""
    print("\n🗄️  Cleaning MinIO storage...")
    
    try:
        # Try to get storage service from registry first
        storage = get_storage_service()
        if storage is None:
            # If registry doesn't have it, create directly
            try:
                storage = StorageService()
            except Exception as e:
                print(f"⚠️  Storage service not available: {e}, skipping...")
                return 0
        
        buckets = ["nda-raw", "nda-processed"]
        total_deleted = 0
        
        for bucket in buckets:
            try:
                print(f"  Cleaning bucket: {bucket}")
                deleted_in_bucket = 0
                
                # Access the MinIO client directly to list all objects
                if hasattr(storage, 'client') and hasattr(storage.client, 'list_objects'):
                    # MinIO client
                    objects = storage.client.list_objects(bucket, recursive=True)
                    for obj in objects:
                        try:
                            storage.delete_file(bucket, obj.object_name)
                            deleted_in_bucket += 1
                        except Exception as e:
                            print(f"    ⚠️  Warning: Could not delete {obj.object_name}: {e}")
                elif hasattr(storage, 's3_client'):
                    # S3 client - list all objects
                    paginator = storage.s3_client.get_paginator('list_objects_v2')
                    pages = paginator.paginate(Bucket=bucket)
                    for page in pages:
                        if 'Contents' in page:
                            for obj in page['Contents']:
                                try:
                                    storage.delete_file(bucket, obj['Key'])
                                    deleted_in_bucket += 1
                                except Exception as e:
                                    print(f"    ⚠️  Warning: Could not delete {obj['Key']}: {e}")
                else:
                    print(f"    ⚠️  Warning: Cannot list objects in bucket {bucket}")
                
                if deleted_in_bucket > 0:
                    print(f"    ✓ Deleted {deleted_in_bucket} objects from {bucket}")
                else:
                    print(f"    ✓ Bucket {bucket} is already empty")
                
                total_deleted += deleted_in_bucket
            except Exception as e:
                print(f"    ⚠️  Warning: Could not clean bucket {bucket}: {e}")
        
        print(f"✓ MinIO storage cleanup complete ({total_deleted} objects deleted)")
        return total_deleted
    except Exception as e:
        print(f"⚠️  Warning: Could not clean MinIO storage: {e}")
        return 0


def clean_opensearch():
    """Delete all documents from OpenSearch"""
    print("\n🔍 Cleaning OpenSearch indices...")
    
    try:
        # Delete all documents by using a match_all query
        delete_result = opensearch_indexer.client.delete_by_query(
            index=opensearch_indexer.index_name,
            body={
                "query": {
                    "match_all": {}
                }
            },
            refresh=True
        )
        
        deleted_count = delete_result.get("deleted", 0)
        print(f"✓ Deleted {deleted_count} documents from OpenSearch")
        return deleted_count
    except Exception as e:
        print(f"⚠️  Warning: Could not clean OpenSearch: {e}")
        # Try to check if index exists
        try:
            if opensearch_indexer.client.indices.exists(index=opensearch_indexer.index_name):
                print(f"    Index exists but deletion failed")
            else:
                print(f"    Index does not exist (already clean)")
        except:
            pass
        return 0


def clean_qdrant():
    """Delete all points from Qdrant collection"""
    print("\n🔮 Cleaning Qdrant collection...")
    
    try:
        # Scroll through all points and delete them
        # We'll use a match_all filter to get all points
        all_points = []
        offset = None
        
        while True:
            scroll_results = qdrant_indexer.client.scroll(
                collection_name=qdrant_indexer.collection_name,
                limit=1000,
                offset=offset
            )
            
            points, next_offset = scroll_results
            
            if not points:
                break
            
            all_points.extend(points)
            
            if next_offset is None:
                break
            
            offset = next_offset
        
        if all_points:
            point_ids = [point.id for point in all_points]
            # Delete in batches
            batch_size = 1000
            deleted_count = 0
            for i in range(0, len(point_ids), batch_size):
                batch = point_ids[i:i + batch_size]
                qdrant_indexer.client.delete(
                    collection_name=qdrant_indexer.collection_name,
                    points_selector=batch
                )
                deleted_count += len(batch)
            
            print(f"✓ Deleted {deleted_count} points from Qdrant")
            return deleted_count
        else:
            print(f"✓ Qdrant collection is already empty")
            return 0
    except Exception as e:
        print(f"⚠️  Warning: Could not clean Qdrant: {e}")
        # Check if collection exists
        try:
            collections = qdrant_indexer.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            if qdrant_indexer.collection_name in collection_names:
                print(f"    Collection exists but deletion failed")
            else:
                print(f"    Collection does not exist (already clean)")
        except:
            pass
        return 0


def clean_all_data(data_dir: str = "data"):
    """Clean all data from the system (preserves PDF files in data/ directory)"""
    print("=" * 60)
    print("🧹 CLEANING ALL DATA FROM SYSTEM")
    print("=" * 60)
    print("NOTE: PDF files in data/ directory are preserved")
    print("=" * 60)
    
    # 1. Clean database
    print("\n1️⃣  Cleaning database...")
    clean_database()
    
    # 2. Clean MinIO storage
    print("\n2️⃣  Cleaning MinIO storage...")
    clean_minio_storage()
    
    # 3. Clean OpenSearch
    print("\n3️⃣  Cleaning OpenSearch...")
    clean_opensearch()
    
    # 4. Clean Qdrant
    print("\n4️⃣  Cleaning Qdrant...")
    clean_qdrant()
    
    print("\n" + "=" * 60)
    print("✅ CLEANUP COMPLETE!")
    print("=" * 60)
    print("\nThe system is now clean and ready for demo.")
    print("You can now upload new files and test Q&A functionality.")


if __name__ == "__main__":
    print("⚠️  WARNING: This will delete ALL data from the system!")
    print("   - All database records")
    print("   - All files in MinIO storage")
    print("   - All OpenSearch indices")
    print("   - All Qdrant collections")
    print()
    print("ℹ️  NOTE: PDF files in data/ directory will be preserved")
    print()
    response = input("Are you sure you want to continue? (yes/no): ")
    if response.lower() == 'yes':
        clean_all_data()
    else:
        print("Cancelled.")

