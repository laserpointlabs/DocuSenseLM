"""
PDF and DOCX parser for NDA documents
"""
import os
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from docx import Document as DocxDocument


class DocumentParser:
    """Parser for PDF and DOCX documents"""

    def __init__(self):
        self.supported_formats = ['.pdf', '.docx']

    def parse(self, file_path: str) -> Dict:
        """
        Parse a document and return extracted text and metadata

        Returns:
            Dict with keys: text, pages, metadata
        """
        file_ext = Path(file_path).suffix.lower()

        if file_ext == '.pdf':
            return self._parse_pdf(file_path)
        elif file_ext == '.docx':
            return self._parse_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")

    def _parse_pdf(self, file_path: str) -> Dict:
        """Parse PDF file"""
        text_by_page = []

        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)

                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    text_by_page.append({
                        'page_num': page_num + 1,
                        'text': text,
                        'is_scanned': len(text.strip()) < 100  # Heuristic: if very little text, likely scanned
                    })

                # Calculate cumulative character spans for each page
                # This allows us to map character positions in the full text to page numbers
                full_text_parts = []
                span_start = 0
                separator = '\n\n'
                for i, page in enumerate(text_by_page):
                    page_text = page['text']
                    page_length = len(page_text)
                    # Add span_start and span_end to each page
                    page['span_start'] = span_start
                    page['span_end'] = span_start + page_length
                    span_start += page_length
                    # Account for separator between pages (we use '\n\n' as separator)
                    # Only add separator if this is not the last page
                    if i < len(text_by_page) - 1:
                        span_start += len(separator)  # Add length of separator
                    full_text_parts.append(page_text)

                # Get metadata
                metadata = pdf_reader.metadata or {}

                return {
                    'text': '\n\n'.join(full_text_parts),
                    'pages': text_by_page,
                    'metadata': {
                        'num_pages': num_pages,
                        'title': metadata.get('/Title', ''),
                        'author': metadata.get('/Author', ''),
                        'subject': metadata.get('/Subject', ''),
                    }
                }
        except Exception as e:
            raise Exception(f"Failed to parse PDF: {e}")

    def _parse_docx(self, file_path: str) -> Dict:
        """Parse DOCX file"""
        try:
            doc = DocxDocument(file_path)

            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)

            text = '\n\n'.join(paragraphs)

            # DOCX doesn't have explicit pages, so we'll create a single page
            pages = [{
                'page_num': 1,
                'text': text,
                'is_scanned': False
            }]

            return {
                'text': text,
                'pages': pages,
                'metadata': {
                    'num_pages': 1,
                    'title': '',
                    'author': '',
                    'subject': '',
                }
            }
        except Exception as e:
            raise Exception(f"Failed to parse DOCX: {e}")


# Global parser instance
parser = DocumentParser()
