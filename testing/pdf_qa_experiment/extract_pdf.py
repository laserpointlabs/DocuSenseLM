#!/usr/bin/env python3
"""
Extract full text from PDF and create expected data structure
"""

import PyPDF2
import json
from pathlib import Path
from datetime import datetime

PDF_FILE = Path(__file__).parent / "fanuc_nda.pdf"
OUTPUT_DIR = Path(__file__).parent

def extract_pdf_text(pdf_path: Path) -> dict:
    """Extract full text from PDF"""
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text_parts = []
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            text_parts.append({
                'page_num': page_num,
                'text': text
            })
        
        full_text = '\n\n'.join([p['text'] for p in text_parts])
        
        return {
            'pages': text_parts,
            'full_text': full_text,
            'num_pages': len(reader.pages),
            'total_chars': len(full_text),
            'estimated_tokens': len(full_text) // 4
        }

def create_expected_data(pdf_text: str) -> dict:
    """
    Create expected data structure based on ontology
    This should be manually verified/updated based on actual PDF content
    """
    # This is a template - should be filled in by examining the actual PDF
    expected = {
        "parties": [
            {
                "name": None,  # To be filled from PDF
                "address": None,
                "type": None  # "disclosing" or "receiving"
            }
        ],
        "governing_law": None,
        "effective_date": None,  # ISO format YYYY-MM-DD
        "expiration_date": None,  # ISO format YYYY-MM-DD
        "term_months": None,
        "survival_months": None,
        "is_mutual": None,  # True/False
        "nda_type": None,  # "mutual" or "unilateral"
        "status": "signed"
    }
    
    # Try to extract some basic info from text
    text_upper = pdf_text.upper()
    
    # Check for mutual/unilateral
    if "MUTUAL" in text_upper:
        expected["is_mutual"] = True
        expected["nda_type"] = "mutual"
    elif "UNILATERAL" in text_upper:
        expected["is_mutual"] = False
        expected["nda_type"] = "unilateral"
    
    # Look for dates (basic pattern matching)
    import re
    date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
    dates = re.findall(date_pattern, pdf_text)
    if dates:
        expected["_found_dates"] = dates  # For manual review
    
    # Look for governing law
    law_patterns = [
        r'governed?\s+by\s+the\s+laws?\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        r'State\s+of\s+([A-Z][a-z]+)',
        r'([A-Z][a-z]+)\s+law'
    ]
    for pattern in law_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            expected["governing_law"] = match.group(1)
            break
    
    return expected

def main():
    print("="*70)
    print("PDF Extraction and Expected Data Creation")
    print("="*70)
    print()
    
    if not PDF_FILE.exists():
        print(f"❌ PDF not found: {PDF_FILE}")
        return
    
    print(f"Extracting from: {PDF_FILE.name}")
    extracted = extract_pdf_text(PDF_FILE)
    
    print(f"\nExtraction Summary:")
    print(f"  Pages: {extracted['num_pages']}")
    print(f"  Characters: {extracted['total_chars']:,}")
    print(f"  Estimated tokens: ~{extracted['estimated_tokens']:,}")
    print()
    
    # Save extracted text
    text_file = OUTPUT_DIR / "extracted_text.txt"
    with open(text_file, 'w') as f:
        f.write(extracted['full_text'])
    print(f"✅ Saved full text to: {text_file.name}")
    
    # Create expected data structure
    expected = create_expected_data(extracted['full_text'])
    
    # Save expected data template
    expected_file = OUTPUT_DIR / "expected_data.json"
    with open(expected_file, 'w') as f:
        json.dump(expected, f, indent=2)
    print(f"✅ Saved expected data template to: {expected_file.name}")
    print()
    print("⚠️  IMPORTANT: Review and update expected_data.json with actual values from the PDF")
    print()
    
    # Show preview of extracted text
    print("First 500 characters of extracted text:")
    print("-"*70)
    print(extracted['full_text'][:500])
    print("...")
    print()

if __name__ == "__main__":
    main()

