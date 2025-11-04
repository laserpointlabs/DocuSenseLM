"""
Main ingestion worker pipeline
Orchestrates: parsing → OCR → chunking → embedding → indexing
"""
import os
import sys
import json
import uuid
from pathlib import Path
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest.parser import parser
from ingest.ocr_detector import ocr_detector
from ingest.ocr_local import local_ocr
from ingest.ocr_aws import get_aws_ocr
from ingest.clause_extractor import clause_extractor
from ingest.chunker import chunker
from ingest.embedder import get_embedder
from ingest.indexer_opensearch import opensearch_indexer
from ingest.indexer_qdrant import qdrant_indexer

from api.services.storage_service import storage_service
from api.db import get_db_session
from api.db.schema import Document, DocumentChunk, Party, DocumentMetadata, DocumentStatus


class IngestionWorker:
    """Main ingestion worker"""

    def __init__(self):
        self.storage = storage_service
        self.embedder = None  # Lazy load
        self.use_textract = os.getenv("USE_TEXTRACT", "false").lower() == "true"

    def ingest_document(self, file_path: str, filename: str, document_id: str = None) -> str:
        """
        Ingest a document through the full pipeline

        Args:
            file_path: Path to the document file
            filename: Original filename
            document_id: Optional document ID (if None, creates new one)

        Returns:
            Document ID (UUID)
        """
        if document_id is None:
            document_id = str(uuid.uuid4())
        else:
            document_id = str(document_id)

        try:
            # 1. Upload to storage (if not already uploaded)
            db = get_db_session()
            s3_path = None
            try:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    s3_path = doc.s3_path
                    if not s3_path:
                        # File wasn't uploaded during upload endpoint, upload it now
                        with open(file_path, 'rb') as f:
                            file_data = f.read()

                        s3_path = self.storage.upload_file(
                            bucket="nda-raw",
                            object_name=f"{document_id}/{filename}",
                            file_data=file_data,
                            content_type="application/pdf" if filename.endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                        doc.s3_path = s3_path
                        db.commit()
                else:
                    # Document doesn't exist, create it and upload file
                    with open(file_path, 'rb') as f:
                        file_data = f.read()

                    s3_path = self.storage.upload_file(
                        bucket="nda-raw",
                        object_name=f"{document_id}/{filename}",
                        file_data=file_data,
                        content_type="application/pdf" if filename.endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
            finally:
                db.close()

            # Ensure s3_path is set
            if not s3_path:
                raise Exception("Failed to get or create s3_path for document")

            # 2. Parse document
            print(f"Parsing document: {filename}")
            parsed = parser.parse(file_path)

            # 3. Check if OCR needed
            if ocr_detector.needs_ocr(parsed['pages']):
                print(f"OCR required for {filename}")
                pages_needing_ocr = ocr_detector.get_pages_needing_ocr(parsed['pages'])

                if self.use_textract:
                    aws_ocr = get_aws_ocr()
                    if aws_ocr:
                        ocr_results = aws_ocr.ocr_pdf(file_path)
                        # Merge OCR results back into pages
                        for ocr_result in ocr_results:
                            page_num = ocr_result['page_num']
                            for page in parsed['pages']:
                                if page['page_num'] == page_num:
                                    page['text'] = ocr_result['text']
                                    page['is_scanned'] = False
                                    break
                else:
                    # Use local Tesseract
                    ocr_results = local_ocr.ocr_pages(file_path, pages_needing_ocr)
                    for ocr_result in ocr_results:
                        page_num = ocr_result['page_num']
                        for page in parsed['pages']:
                            if page['page_num'] == page_num:
                                page['text'] = ocr_result['text']
                                page['is_scanned'] = False
                                break

            # Rebuild full text from pages
            full_text = '\n\n'.join([p['text'] for p in parsed['pages']])

            # 4. Extract clauses and metadata
            print(f"Extracting clauses from {filename}")
            extracted = clause_extractor.extract(full_text, parsed['pages'])

            # 5. Chunk document
            print(f"Chunking document: {filename}")
            chunks = chunker.chunk_document(extracted, document_id, s3_path)

            # 6. Generate embeddings
            print(f"Generating embeddings for {len(chunks)} chunks")
            if self.embedder is None:
                self.embedder = get_embedder()

            chunk_texts = [chunk.text for chunk in chunks]
            embeddings = self.embedder.embed_batch(chunk_texts)

            # 7. Store in PostgreSQL
            print(f"Storing in database: {filename}")
            db = get_db_session()
            try:
                # Get or create document record
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    # Update existing document
                    doc.filename = filename
                    doc.status = DocumentStatus.PROCESSING
                    doc.s3_path = s3_path
                    doc.metadata_json = parsed.get('metadata', {})
                else:
                    # Create new document record
                    doc = Document(
                        id=document_id,
                        filename=filename,
                        status=DocumentStatus.PROCESSING,
                        s3_path=s3_path,
                        metadata_json=parsed.get('metadata', {})
                    )
                    db.add(doc)

                # Delete existing chunks for this document (in case of re-indexing)
                db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()

                # Create chunks
                for i, chunk in enumerate(chunks):
                    chunk_db = DocumentChunk(
                        document_id=document_id,
                        chunk_index=chunk.chunk_index,
                        section_type=chunk.section_type,
                        clause_number=chunk.clause_number,
                        clause_title=getattr(chunk, 'clause_title', None),  # Store clause title if available
                        text=chunk.text,
                        page_num=chunk.page_num,
                        span_start=chunk.span_start,
                        span_end=chunk.span_end
                    )
                    db.add(chunk_db)

                # Create parties - filter out invalid party names first
                valid_parties = []
                for party_info in extracted['metadata'].get('parties', []):
                    party_name = party_info.get('name', '') or party_info.get('party_name', '')
                    party_type = party_info.get('type')

                    # Skip if no name or name is too short/generic
                    if not party_name or len(party_name.strip()) < 3:
                        continue

                    # Skip if name looks like sentence fragment (too long, no proper nouns)
                    if len(party_name) > 100 or party_name.lower() in ['the parties', 'delivered', 'executed', 'supersedes']:
                        continue

                    # Ensure party_type is valid (disclosing or receiving)
                    if party_type not in ['disclosing', 'receiving']:
                        # Try to infer from name or context
                        name_lower = party_name.lower()
                        if any(word in name_lower for word in ['disclos', 'disclosing']):
                            party_type = 'disclosing'
                        elif any(word in name_lower for word in ['recipient', 'receiving', 'receiver']):
                            party_type = 'receiving'
                        else:
                            # Default to disclosing if company name detected, else receiving
                            if any(word in name_lower for word in ['company', 'corp', 'inc', 'llc', 'ltd']):
                                party_type = 'disclosing'
                            else:
                                party_type = 'receiving'

                    valid_parties.append({
                        'name': party_name.strip(),
                        'type': party_type,
                        'address': party_info.get('address')
                    })

                # Only create parties if we have valid ones
                for party_info in valid_parties:
                    party = Party(
                        document_id=document_id,
                        party_name=party_info['name'],
                        party_type=party_info['type'],
                        address=party_info.get('address')
                    )
                    db.add(party)

                # Create or update metadata
                metadata = extracted['metadata']
                doc_metadata = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
                if doc_metadata:
                    # Update existing metadata
                    doc_metadata.effective_date = metadata.get('effective_date')
                    doc_metadata.governing_law = metadata.get('governing_law')
                    doc_metadata.is_mutual = metadata.get('is_mutual')
                    doc_metadata.term_months = metadata.get('term_months')
                    doc_metadata.survival_months = metadata.get('survival_months')
                else:
                    # Create new metadata
                    doc_metadata = DocumentMetadata(
                        document_id=document_id,
                        effective_date=metadata.get('effective_date'),
                        governing_law=metadata.get('governing_law'),
                        is_mutual=metadata.get('is_mutual'),
                        term_months=metadata.get('term_months'),
                        survival_months=metadata.get('survival_months')
                    )
                    db.add(doc_metadata)

                db.commit()
            finally:
                db.close()

            # 8. Index to OpenSearch and Qdrant
            print(f"Indexing to search engines: {filename}")
            chunk_dicts = [
                {
                    "id": str(uuid.uuid4()),
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "text": chunk.text,
                    "section_type": chunk.section_type,
                    "clause_number": chunk.clause_number,
                    "page_num": chunk.page_num,
                    "span_start": chunk.span_start,
                    "span_end": chunk.span_end,
                    "source_uri": chunk.source_uri
                }
                for chunk in chunks
            ]

            opensearch_indexer.index_chunks(chunk_dicts, extracted['metadata'])
            qdrant_indexer.index_chunks(chunk_dicts, embeddings)

            # 9. Store normalized JSON
            normalized_json = {
                "document_id": document_id,
                "filename": filename,
                "title": extracted.get('title'),
                "recitals": extracted.get('recitals', []),
                "clauses": extracted.get('clauses', []),
                "metadata": extracted.get('metadata', {}),
                "chunks": [
                    {
                        "chunk_index": chunk.chunk_index,
                        "section_type": chunk.section_type,
                        "clause_number": chunk.clause_number,
                        "text": chunk.text,
                        "page_num": chunk.page_num,
                        "span_start": chunk.span_start,
                        "span_end": chunk.span_end
                    }
                    for chunk in chunks
                ]
            }

            json_data = json.dumps(normalized_json, indent=2, default=str)
            self.storage.upload_file(
                bucket="nda-processed",
                object_name=f"{document_id}/nda_record.json",
                file_data=json_data.encode('utf-8'),
                content_type="application/json"
            )

            # 10. Update document status
            db = get_db_session()
            try:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.status = DocumentStatus.PROCESSED
                    db.commit()
            finally:
                db.close()

            print(f"Ingestion complete for {filename}")
            return document_id

        except Exception as e:
            # Update status to failed
            db = get_db_session()
            try:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.status = DocumentStatus.FAILED
                    db.commit()
            finally:
                db.close()

            raise Exception(f"Ingestion failed for {filename}: {e}")


# Global worker instance
worker = IngestionWorker()
