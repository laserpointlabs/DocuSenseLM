#!/usr/bin/env python3
"""RAG pipeline audit script.

Collects statistics about stored NDAs (document metadata, chunk sizes,
section distribution, governing-law coverage, etc.) to help tune retrieval
and ranking heuristics.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from statistics import mean, median

from api.db import get_db_session
from api.db.schema import Document, DocumentChunk, DocumentMetadata, DocumentStatus


def _chunk_length(chunk: DocumentChunk) -> int:
    if chunk.span_end and chunk.span_end > chunk.span_start:
        return chunk.span_end - chunk.span_start
    if chunk.text:
        return len(chunk.text)
    return 0


def gather_statistics(limit: int | None = None) -> dict:
    session = get_db_session()
    try:
        docs_q = session.query(Document)
        if limit:
            docs_q = docs_q.limit(limit)
        documents = docs_q.all()
        document_ids = [doc.id for doc in documents]

        chunk_q = session.query(DocumentChunk)
        if document_ids:
            chunk_q = chunk_q.filter(DocumentChunk.document_id.in_(document_ids))
        chunks = chunk_q.all()

        metadata_q = session.query(DocumentMetadata)
        if document_ids:
            metadata_q = metadata_q.filter(DocumentMetadata.document_id.in_(document_ids))
        metadata_rows = metadata_q.all()

    finally:
        session.close()

    chunk_lengths = [_chunk_length(chunk) for chunk in chunks if _chunk_length(chunk) > 0]
    section_counts = Counter(chunk.section_type or "unknown" for chunk in chunks)

    governing_counts = Counter(
        (row.governing_law or "(unspecified)").strip() or "(unspecified)"
        for row in metadata_rows
    )
    mutual_counts = Counter(
        "mutual" if row.is_mutual else "unilateral" if row.is_mutual is False else "unset"
        for row in metadata_rows
    )

    stats = {
        "documents": {
            "total": len(documents),
            "processed": sum(1 for doc in documents if doc.status == DocumentStatus.PROCESSED),
            "failed": sum(1 for doc in documents if doc.status == DocumentStatus.FAILED),
        },
        "chunks": {
            "total": len(chunks),
            "by_section_type": dict(section_counts.most_common()),
            "length": {
                "min": min(chunk_lengths) if chunk_lengths else 0,
                "max": max(chunk_lengths) if chunk_lengths else 0,
                "mean": mean(chunk_lengths) if chunk_lengths else 0,
                "median": median(chunk_lengths) if chunk_lengths else 0,
            },
        },
        "metadata": {
            "rows": len(metadata_rows),
            "governing_law": dict(governing_counts.most_common()),
            "mutuality": dict(mutual_counts.most_common()),
        },
    }

    return stats


def print_report(stats: dict) -> None:
    print("=== RAG Pipeline Audit ===")
    print("Documents:")
    print(f"  Total:     {stats['documents']['total']}")
    print(f"  Processed: {stats['documents']['processed']}")
    print(f"  Failed:    {stats['documents']['failed']}")

    print("\nChunks:")
    print(f"  Total: {stats['chunks']['total']}")
    length = stats['chunks']['length']
    print(f"  Length (chars): min={length['min']} median={length['median']} mean={length['mean']:.1f} max={length['max']}")

    print("  Section distribution:")
    for section, count in stats['chunks']['by_section_type'].items():
        print(f"    {section or '(unknown)'}: {count}")

    print("\nMetadata:")
    print(f"  Rows: {stats['metadata']['rows']}")

    print("  Governing law:")
    for law, count in stats['metadata']['governing_law'].items():
        print(f"    {law}: {count}")

    print("  Mutuality:")
    for mutual, count in stats['metadata']['mutuality'].items():
        print(f"    {mutual}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit chunking/metadata for retrieval tuning")
    parser.add_argument("--limit", type=int, help="Optional limit on number of documents to inspect")
    parser.add_argument("--output", type=str, help="Optional JSON file to store the stats")

    args = parser.parse_args()
    stats = gather_statistics(limit=args.limit)
    print_report(stats)
    
    if args.output:
        with open(args.output, 'w') as fh:
            json.dump(stats, fh, indent=2, default=str)
        print(f"\nStats written to {args.output}")


if __name__ == "__main__":
    main()
