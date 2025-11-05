"""
Clause-level chunking with provenance tracking
"""
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Chunk:
    """Represents a chunk of text with provenance"""
    text: str
    chunk_index: int
    document_id: str
    section_type: str
    clause_number: Optional[str]
    page_num: int
    span_start: int
    span_end: int
    source_uri: str
    clause_title: Optional[str] = None  # Store the extracted clause title (must be last due to default value)


class Chunker:
    """Chunk documents at clause level with provenance tracking"""

    def __init__(self):
        self.min_chunk_size = 50  # Minimum characters per chunk
        self.max_chunk_size = 2000  # Maximum characters per chunk

    def chunk_document(
        self,
        extracted_data: Dict,
        document_id: str,
        source_uri: str
    ) -> List[Chunk]:
        """
        Chunk extracted document data into clause-level chunks

        Args:
            extracted_data: Dict from clause_extractor with keys: title, recitals, clauses, metadata
            document_id: UUID of the document
            source_uri: Source URI (e.g., s3://bucket/key or file path)

        Returns:
            List of Chunk objects
        """
        chunks = []
        chunk_index = 0

        # Chunk title
        if extracted_data.get('title'):
            title_chunk = Chunk(
                text=extracted_data['title'],
                chunk_index=chunk_index,
                document_id=document_id,
                section_type='title',
                clause_number=None,
                page_num=1,
                span_start=0,
                span_end=len(extracted_data['title']),
                source_uri=source_uri
            )
            chunks.append(title_chunk)
            chunk_index += 1

        # Chunk recitals
        for recital in extracted_data.get('recitals', []):
            recital_chunk = Chunk(
                text=recital['text'],
                chunk_index=chunk_index,
                document_id=document_id,
                section_type='recital',
                clause_number=recital.get('clause_number'),
                page_num=recital.get('page_num', 1),
                span_start=recital.get('span_start', 0),
                span_end=recital.get('span_end', len(recital['text'])),
                source_uri=source_uri
            )
            chunks.append(recital_chunk)
            chunk_index += 1

        # Add a special "parties" chunk with party names and addresses for searchability
        metadata = extracted_data.get('metadata', {})
        parties_list = metadata.get('parties', [])
        if parties_list:
            parties_text_parts = []
            for party in parties_list:
                party_name = party.get('name', '')
                party_address = party.get('address', '')
                party_type = party.get('type', '')

                if party_name:
                    party_info = f"Party: {party_name}"
                    if party_type:
                        party_info += f" (Type: {party_type})"
                    if party_address:
                        party_info += f" Address: {party_address}"
                    parties_text_parts.append(party_info)

            if parties_text_parts:
                parties_text = " | ".join(parties_text_parts)
                parties_chunk = Chunk(
                    text=parties_text,
                    chunk_index=chunk_index,
                    document_id=document_id,
                    section_type='parties',
                    clause_number=None,
                    page_num=1,  # Usually on first page
                    span_start=0,
                    span_end=len(parties_text),
                    source_uri=source_uri
                )
                chunks.append(parties_chunk)
                chunk_index += 1

        # Chunk clauses
        for clause in extracted_data.get('clauses', []):
            clause_text = clause['text']

            # If clause is too large, split it into sub-chunks
            if len(clause_text) > self.max_chunk_size:
                sub_chunks = self._split_large_clause(
                    clause_text,
                    clause,
                    document_id,
                    source_uri,
                    chunk_index
                )
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
            else:
                clause_chunk = Chunk(
                    text=clause_text,
                    chunk_index=chunk_index,
                    document_id=document_id,
                    section_type='clause',
                    clause_number=clause.get('clause_number'),
                    clause_title=clause.get('title'),  # Store the extracted title
                    page_num=clause.get('page_num', 1),
                    span_start=clause.get('span_start', 0),
                    span_end=clause.get('span_end', len(clause_text)),
                    source_uri=source_uri
                )
                chunks.append(clause_chunk)
                chunk_index += 1

        return chunks

    def _split_large_clause(
        self,
        clause_text: str,
        clause_meta: Dict,
        document_id: str,
        source_uri: str,
        start_chunk_index: int
    ) -> List[Chunk]:
        """Split a large clause into smaller chunks"""
        chunks = []
        current_pos = 0
        chunk_index = start_chunk_index

        # Split by paragraphs first
        paragraphs = clause_text.split('\n\n')
        current_chunk_text = []
        current_chunk_length = 0

        for para in paragraphs:
            para_length = len(para)

            # If adding this paragraph would exceed max, save current chunk
            if current_chunk_length + para_length > self.max_chunk_size and current_chunk_text:
                chunk_text = '\n\n'.join(current_chunk_text)
                if len(chunk_text) >= self.min_chunk_size:
                    chunk = Chunk(
                        text=chunk_text,
                        chunk_index=chunk_index,
                        document_id=document_id,
                        section_type='clause',
                        clause_number=clause_meta.get('clause_number'),
                        page_num=clause_meta.get('page_num', 1),
                        span_start=current_pos,
                        span_end=current_pos + len(chunk_text),
                        source_uri=source_uri
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    current_pos += len(chunk_text)
                    current_chunk_text = []
                    current_chunk_length = 0

                # If single paragraph is too large, split by sentences
                if para_length > self.max_chunk_size:
                    sentence_chunks = self._split_by_sentences(
                        para,
                        clause_meta,
                        document_id,
                        source_uri,
                        current_pos,
                        chunk_index
                    )
                    chunks.extend(sentence_chunks)
                    chunk_index += len(sentence_chunks)
                    current_pos += para_length
                else:
                    current_chunk_text.append(para)
                    current_chunk_length += para_length
            else:
                current_chunk_text.append(para)
                current_chunk_length += para_length

        # Add remaining chunk
        if current_chunk_text:
            chunk_text = '\n\n'.join(current_chunk_text)
            if len(chunk_text) >= self.min_chunk_size:
                chunk = Chunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    document_id=document_id,
                    section_type='clause',
                    clause_number=clause_meta.get('clause_number'),
                    page_num=clause_meta.get('page_num', 1),
                    span_start=current_pos,
                    span_end=current_pos + len(chunk_text),
                    source_uri=source_uri
                )
                chunks.append(chunk)

        return chunks

    def _split_by_sentences(
        self,
        text: str,
        clause_meta: Dict,
        document_id: str,
        source_uri: str,
        start_pos: int,
        start_chunk_index: int
    ) -> List[Chunk]:
        """Split text by sentences when paragraphs are too large"""
        import re
        sentences = re.split(r'[.!?]+\s+', text)
        chunks = []
        current_chunk = []
        current_pos = start_pos
        chunk_index = start_chunk_index

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(' '.join(current_chunk)) + len(sentence) > self.max_chunk_size:
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    chunk = Chunk(
                        text=chunk_text,
                        chunk_index=chunk_index,
                        document_id=document_id,
                        section_type='clause',
                        clause_number=clause_meta.get('clause_number'),
                        page_num=clause_meta.get('page_num', 1),
                        span_start=current_pos,
                        span_end=current_pos + len(chunk_text),
                        source_uri=source_uri
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    current_pos += len(chunk_text)
                    current_chunk = []

            current_chunk.append(sentence)

        # Add remaining chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk = Chunk(
                text=chunk_text,
                chunk_index=chunk_index,
                document_id=document_id,
                section_type='clause',
                clause_number=clause_meta.get('clause_number'),
                page_num=clause_meta.get('page_num', 1),
                span_start=current_pos,
                span_end=current_pos + len(chunk_text),
                source_uri=source_uri
            )
            chunks.append(chunk)

        return chunks


# Global chunker instance
chunker = Chunker()
