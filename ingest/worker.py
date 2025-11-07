"""
Main ingestion worker pipeline
Orchestrates: parsing → OCR → chunking → embedding → indexing
"""
import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from ingest.parser import parser
from ingest.ocr_detector import ocr_detector
from ingest.ocr_local import local_ocr
from ingest.ocr_aws import get_aws_ocr
from ingest.clause_extractor import clause_extractor
from ingest.chunker import chunker
from ingest.embedder import get_embedder
from ingest.llm_refiner import refine_metadata
import api.services.storage_service  # ensure default storage registration
import ingest.indexer_opensearch  # ensure BM25 backend registered
import ingest.indexer_qdrant  # ensure vector backend registered

from api.services.service_registry import (
    get_storage_service,
    get_bm25_indexer,
    get_vector_indexer,
    _services,
)
from api.db import get_db_session
from api.db.schema import Document, DocumentChunk, DocumentMetadata, DocumentStatus, Party
from api.services.registry_service import registry_service


class IngestionWorker:
    """Main ingestion worker"""

    def __init__(self):
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
        file_bytes = Path(file_path).read_bytes()
        file_sha256 = hashlib.sha256(file_bytes).digest()

        existing_doc = None
        db = get_db_session()
        try:
            existing_doc = db.query(Document).filter(Document.file_sha256 == file_sha256).first()
        finally:
            db.close()

        if document_id is None and existing_doc:
            return str(existing_doc.id)

        if document_id is None:
            document_uuid = uuid.uuid4()
            document_id = str(document_uuid)
        else:
            document_id = str(document_id)
            document_uuid = uuid.UUID(document_id)
            if existing_doc and existing_doc.id != document_uuid:
                raise ValueError("A document with identical contents already exists")

        try:
            # 1. Upload to storage (if not already uploaded)
            db = get_db_session()
            s3_path = None
            try:
                try:
                    storage = get_storage_service()
                except Exception as exc:
                    raise RuntimeError(
                        f"Storage service unavailable during upload: {exc}; registry keys={list(_services.keys())}"
                    ) from exc
                if storage is None:  # pragma: no cover - defensive
                    raise RuntimeError("Storage service resolved to None")
                doc = db.query(Document).filter(Document.id == document_uuid).first()
                if doc:
                    s3_path = doc.s3_path
                    if not s3_path:
                        s3_path = storage.upload_file(
                            bucket="nda-raw",
                            object_name=f"{document_id}/{filename}",
                            file_data=file_bytes,
                            content_type=self._infer_content_type(filename)
                        )
                        doc.s3_path = s3_path
                    doc.file_sha256 = file_sha256
                    db.commit()
                else:
                    # Document doesn't exist, create it and upload file
                    try:
                        storage = get_storage_service()
                    except Exception as exc:
                        raise RuntimeError(
                            f"Storage service unavailable during metadata update: {exc}; registry keys={list(_services.keys())}"
                        ) from exc
                    s3_path = storage.upload_file(
                        bucket="nda-raw",
                        object_name=f"{document_id}/{filename}",
                        file_data=file_bytes,
                        content_type=self._infer_content_type(filename)
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

            metadata_refinement_info = None
            try:
                refined_metadata, refinement_info = refine_metadata(extracted.get('metadata', {}), full_text)
                extracted['metadata'] = refined_metadata
                metadata_refinement_info = refinement_info
                if refinement_info:
                    extracted['metadata']['llm_refinement'] = refinement_info
            except Exception as exc:  # pragma: no cover - refinement failure path
                print(f"Warning: LLM refinement failed for {filename}: {exc}")

            # 5. Chunk document
            print(f"Chunking document: {filename}")
            chunks = chunker.chunk_document(extracted, document_id, s3_path)

            # 6. Generate embeddings
            print(f"Generating embeddings for {len(chunks)} chunks")
            # Embeddings will be generated later with contextual text (Phase 3)
            # 7. Store in PostgreSQL
            print(f"Storing in database: {filename}")
            db = get_db_session()
            try:
                # Get or create document record
                doc = db.query(Document).filter(Document.id == document_uuid).first()
                if doc:
                    # Update existing document
                    doc.filename = filename
                    doc.status = DocumentStatus.PROCESSING
                    doc.s3_path = s3_path
                    doc.metadata_json = parsed.get('metadata', {})
                else:
                    # Create new document record
                    doc = Document(
                        id=document_uuid,
                        filename=filename,
                        status=DocumentStatus.PROCESSING,
                        s3_path=s3_path,
                        metadata_json=parsed.get('metadata', {}),
                        file_sha256=file_sha256
                    )
                    db.add(doc)

                # Delete existing chunks for this document (in case of re-indexing)
                db.query(DocumentChunk).filter(DocumentChunk.document_id == document_uuid).delete()

                # Create chunks
                for i, chunk in enumerate(chunks):
                    chunk_db = DocumentChunk(
                        document_id=document_uuid,
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
                        document_id=document_uuid,
                        party_name=party_info['name'],
                        party_type=party_info['type'],
                        address=party_info.get('address')
                    )
                    db.add(party)

                # Create or update metadata
                metadata = extracted['metadata']
                doc_metadata = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_uuid).first()
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
                        document_id=document_uuid,
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
            
            # Build contextual text for embeddings (Phase 3: Contextual Embeddings)
            # Prepend metadata to chunks before embedding for better retrieval
            contextual_texts = []
            chunk_dicts = []
            for chunk in chunks:
                chunk_dict = {
                    "id": str(uuid.uuid4()),
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "text": chunk.text,
                    "section_type": chunk.section_type,
                    "clause_number": chunk.clause_number,
                    "clause_title": getattr(chunk, 'clause_title', None),
                    "page_num": chunk.page_num,
                    "span_start": chunk.span_start,
                    "span_end": chunk.span_end,
                    "source_uri": chunk.source_uri
                }
                chunk_dicts.append(chunk_dict)
                
                # Build contextual text for embedding
                context_parts = []
                metadata = extracted.get('metadata', {})
                
                # Add document-level metadata context
                parties = metadata.get("parties", [])
                if parties:
                    party_names = [p.get("name", "") if isinstance(p, dict) else str(p) for p in parties]
                    party_str = ", ".join([p for p in party_names if p])
                    if party_str:
                        context_parts.append(f"Parties: {party_str}")
                
                governing_law = metadata.get("governing_law")
                if governing_law:
                    context_parts.append(f"Governing Law: {governing_law}")
                
                effective_date = metadata.get("effective_date")
                if effective_date:
                    if isinstance(effective_date, str):
                        context_parts.append(f"Effective Date: {effective_date}")
                    else:
                        context_parts.append(f"Effective Date: {effective_date.strftime('%B %d, %Y')}")
                
                is_mutual = metadata.get("is_mutual")
                if is_mutual is not None:
                    context_parts.append(f"Type: {'mutual' if is_mutual else 'unilateral'}")
                
                term_months = metadata.get("term_months")
                if term_months:
                    if term_months >= 12:
                        years = term_months // 12
                        context_parts.append(f"Term: {years} {'year' if years == 1 else 'years'}")
                    else:
                        context_parts.append(f"Term: {term_months} {'month' if term_months == 1 else 'months'}")
                
                # Add clause title if available
                clause_title = getattr(chunk, 'clause_title', None)
                if clause_title:
                    context_parts.append(f"Clause: {clause_title}")
                elif chunk.clause_number:
                    context_parts.append(f"Clause: {chunk.clause_number}")
                
                # Build contextual text: metadata context + original text
                if context_parts:
                    context_prefix = " | ".join(context_parts)
                    contextual_text = f"[{context_prefix}] {chunk.text}"
                else:
                    contextual_text = chunk.text
                
                contextual_texts.append(contextual_text)
            
            # Generate embeddings from contextual text (not just original text)
            embedder = get_embedder()
            embeddings = embedder.embed_batch(contextual_texts)

            bm25_indexer = get_bm25_indexer()
            vector_indexer = get_vector_indexer()
            bm25_indexer.index_chunks(chunk_dicts, extracted['metadata'])
            vector_indexer.index_chunks(chunk_dicts, embeddings, extracted['metadata'])

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
            storage = get_storage_service()
            if storage is None:
                raise RuntimeError(
                    f"Storage service resolved to None; registry keys={list(_services.keys())}"
                )
            storage.upload_file(
                bucket="nda-processed",
                object_name=f"{document_id}/nda_record.json",
                file_data=json_data.encode('utf-8'),
                content_type="application/json"
            )

            # 10. Update document status
            db = get_db_session()
            try:
                doc = db.query(Document).filter(Document.id == document_uuid).first()
                if doc:
                    doc.status = DocumentStatus.PROCESSED
                    
                    # Auto-generate test questions for this document
                    try:
                        from scripts.generate_questions_with_answers import generate_questions_with_answers, create_question_with_answer
                        from api.db.schema import CompetencyQuestion
                        
                        questions = generate_questions_with_answers(document_id, filename)
                        for q in questions:
                            # Check if question already exists
                            existing = db.query(CompetencyQuestion).filter(
                                CompetencyQuestion.question_text == q["question"],
                                CompetencyQuestion.document_id == document_id
                            ).first()
                            
                            if not existing:
                                create_question_with_answer(
                                    question_text=q["question"],
                                    expected_answer=q["expected_answer"],
                                    document_id=q["document_id"],
                                    verification_hint=q.get("verification_hint"),
                                    expected_clause=q.get("expected_clause"),
                                    expected_page=q.get("expected_page"),
                                    auto_generated=True
                                )
                        if questions:
                            print(f"✅ Auto-generated {len(questions)} test questions for {filename}")
                    except Exception as e:
                        print(f"⚠️  Warning: Failed to auto-generate questions: {e}")
                        # Don't fail ingestion if question generation fails
                    doc.file_sha256 = file_sha256
                    db.commit()
            finally:
                db.close()

            # 11. Update NDA registry
            self._upsert_registry_record(
                document_id=document_id,
                metadata=metadata,
                s3_path=s3_path,
                file_bytes=file_bytes,
                full_text=full_text
            )

            print(f"Ingestion complete for {filename}")
            return document_id

        except Exception as e:
            # Update status to failed
            db = get_db_session()
            try:
                doc = db.query(Document).filter(Document.id == document_uuid).first()
                if doc:
                    doc.status = DocumentStatus.FAILED
                    db.commit()
            finally:
                db.close()

            raise Exception(f"Ingestion failed for {filename}: {e}")

    def _infer_content_type(self, filename: str) -> str:
        """Infer MIME type from filename."""
        lower = filename.lower()
        if lower.endswith(".pdf"):
            return "application/pdf"
        if lower.endswith(".docx"):
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if lower.endswith(".doc"):
            return "application/msword"
        return "application/octet-stream"

    def _select_counterparty(self, metadata: Dict) -> str:
        """Select the best available counterparty name."""
        parties = metadata.get('parties') or []
        for party in parties:
            name = party.get('name') or party.get('party_name')
            if name:
                return name.strip()
        return "Unknown Counterparty"

    def _upsert_registry_record(
        self,
        *,
        document_id: str,
        metadata: Dict,
        s3_path: str,
        file_bytes: bytes,
        full_text: str
    ) -> None:
        """Persist normalized NDA record for deterministic lookups."""
        effective_date = metadata.get('effective_date')
        if isinstance(effective_date, datetime):
            effective_date = effective_date.date()

        term_months = metadata.get('term_months')
        survival_months = metadata.get('survival_months')

        tags = {
            "governing_law": metadata.get('governing_law'),
            "is_mutual": metadata.get('is_mutual'),
            "survival_months": survival_months,
            "term_months": term_months,
        }

        facts_payload = {
            "metadata": metadata,
            "stats": {
                "party_count": len(metadata.get('parties') or []),
            },
        }

        registry_service.upsert_record(
            document_id=document_id,
            counterparty_name=self._select_counterparty(metadata),
            counterparty_domain=metadata.get('counterparty_domain'),
            entity_id=metadata.get('entity_id'),
            owner_user_id=metadata.get('owner_user_id'),
            direction=metadata.get('direction'),
            nda_type="mutual" if metadata.get('is_mutual') else "one_way" if metadata.get('is_mutual') is not None else None,
            effective_date=effective_date,
            term_months=term_months,
            survival_months=survival_months,
            status="signed",
            file_uri=s3_path,
            file_bytes=file_bytes,
            extracted_text=full_text,
            tags=tags,
            facts=facts_payload,
        )


# Global worker instance
worker = IngestionWorker()


def main():
    """Keep the module alive when invoked as a script."""
    import logging
    import time

    logging.basicConfig(level=logging.INFO)
    logging.info("Ingestion worker container ready – invoke ingest.worker.worker.ingest_document() via API/tests.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:  # pragma: no cover
        logging.info("Ingestion worker shutting down.")


if __name__ == "__main__":  # pragma: no cover
    main()
