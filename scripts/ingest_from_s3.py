#!/usr/bin/env python3
"""
Batch ingest documents from S3 bucket
"""
import os
import sys
import argparse
import boto3
from pathlib import Path
import tempfile

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingest.worker import worker


def list_s3_files(bucket_name: str, prefix: str = "") -> list:
    """List files in S3 bucket"""
    s3_client = boto3.client('s3')
    files = []

    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    for page in pages:
        if 'Contents' in page:
            for obj in page['Contents']:
                if obj['Key'].endswith(('.pdf', '.docx')):
                    files.append(obj['Key'])

    return files


def download_from_s3(bucket_name: str, key: str, local_path: str):
    """Download file from S3"""
    s3_client = boto3.client('s3')
    s3_client.download_file(bucket_name, key, local_path)


def ingest_from_s3(bucket_name: str, prefix: str = "", limit: int = None):
    """
    Ingest documents from S3 bucket

    Args:
        bucket_name: S3 bucket name
        prefix: S3 prefix to filter files
        limit: Maximum number of files to process (None for all)
    """
    print(f"Listing files in s3://{bucket_name}/{prefix}...")
    files = list_s3_files(bucket_name, prefix)

    if limit:
        files = files[:limit]

    print(f"Found {len(files)} files to ingest")

    success_count = 0
    error_count = 0

    for idx, file_key in enumerate(files, 1):
        print(f"\n[{idx}/{len(files)}] Processing: {file_key}")

        try:
            # Download to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_key).suffix) as tmp:
                temp_path = tmp.name
                download_from_s3(bucket_name, file_key, temp_path)

            # Ingest
            filename = Path(file_key).name
            document_id = worker.ingest_document(temp_path, filename)
            print(f"  ✓ Ingested: {document_id}")
            success_count += 1

            # Clean up temp file
            os.unlink(temp_path)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            error_count += 1

    print(f"\n{'='*60}")
    print(f"Ingestion complete:")
    print(f"  Success: {success_count}")
    print(f"  Errors:  {error_count}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description='Ingest documents from S3')
    parser.add_argument('bucket', help='S3 bucket name')
    parser.add_argument('--prefix', default='', help='S3 prefix (default: "")')
    parser.add_argument('--limit', type=int, help='Maximum number of files to process')

    args = parser.parse_args()

    ingest_from_s3(args.bucket, args.prefix, args.limit)


if __name__ == '__main__':
    main()
