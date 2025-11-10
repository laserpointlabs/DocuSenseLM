#!/usr/bin/env python3
"""
Test script for PDF text matching using LLM.
This script loads a PDF, extracts text items, and tests the matching logic.
"""

import sys
import os
import asyncio
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    import PyPDF2
except ImportError:
    print("PyPDF2 not found. This script should run in the Docker container.")
    sys.exit(1)

from llm.llm_factory import get_llm_client
from llm.llm_client import Chunk
import re


def extract_pdf_text_items_simulate_pdfjs(pdf_path: str, page_num: int = 0):
    """
    Simulate PDF.js text extraction by splitting text into granular items.
    PDF.js often splits text at character or word boundaries.
    """
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        if page_num >= len(pdf_reader.pages):
            raise ValueError(f"Page {page_num} not found. PDF has {len(pdf_reader.pages)} pages.")
        
        page = pdf_reader.pages[page_num]
        full_text = page.extract_text()
    
    # Simulate PDF.js behavior: split text into items
    # PDF.js often splits on spaces, punctuation, and sometimes characters
    text_items = []
    index = 0
    
    # Method 1: Split by whitespace and punctuation (most common)
    import re
    # Split on word boundaries but keep separators
    tokens = re.findall(r'\S+|\s+', full_text)
    
    for token in tokens:
        if token.strip():  # Non-whitespace
            text_items.append({
                "str": token,
                "index": index
            })
            index += 1
        else:  # Whitespace
            # Sometimes PDF.js includes spaces as separate items
            text_items.append({
                "str": token,
                "index": index
            })
            index += 1
    
    return text_items


def extract_pdf_text_items_char_level(pdf_path: str, page_num: int = 0):
    """
    Extract text character by character to simulate very granular PDF.js splitting.
    """
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        if page_num >= len(pdf_reader.pages):
            raise ValueError(f"Page {page_num} not found. PDF has {len(pdf_reader.pages)} pages.")
        
        page = pdf_reader.pages[page_num]
        full_text = page.extract_text()
    
    text_items = []
    for i, char in enumerate(full_text):
        text_items.append({
            "str": char,
            "index": i
        })
    
    return text_items


def extract_pdf_text_items_word_level(pdf_path: str, page_num: int = 0):
    """
    Extract text word by word (simpler approach).
    """
    with open(pdf_path, 'rb') as f:
        pdf_reader = PyPDF2.PdfReader(f)
        if page_num >= len(pdf_reader.pages):
            raise ValueError(f"Page {page_num} not found. PDF has {len(pdf_reader.pages)} pages.")
        
        page = pdf_reader.pages[page_num]
        full_text = page.extract_text()
    
    # Split by whitespace
    words = full_text.split()
    text_items = []
    
    for i, word in enumerate(words):
        text_items.append({
            "str": word,
            "index": i
        })
    
    return text_items


async def test_llm_matching(chunk_text: str, pdf_text_items: list, document_id: str = "test-doc"):
    """Test LLM matching with given text and PDF items."""
    from llm.llm_factory import get_llm_client
    
    # Find where the chunk text might appear in the PDF items
    # Search through all items, not just first 100
    # Normalize: remove spaces, commas, hyphens, newlines for matching
    chunk_normalized = chunk_text.lower().replace(" ", "").replace(",", "").replace("-", "").replace("\n", "")
    
    # Find potential match location
    potential_start = None
    for i in range(len(pdf_text_items) - 5):
        window = pdf_text_items[i:i+20]
        combined = "".join([item.get('str', '') for item in window]).lower().replace(" ", "").replace(",", "").replace("-", "").replace("\n", "")
        if chunk_normalized in combined:
            potential_start = max(0, i - 10)  # Show some context before
            break
    
    # Show items around the potential match (or first 100 if not found)
    if potential_start is not None:
        show_start = potential_start
        show_end = min(len(pdf_text_items), potential_start + 120)  # Show 120 items around match
    else:
        show_start = 0
        show_end = min(100, len(pdf_text_items))
    
    pdf_text_with_indices = "\n".join([
        f"[{show_start + i}] '{item.get('str', '')}'"
        for i, item in enumerate(pdf_text_items[show_start:show_end])
    ])
    
    # Also show what the text looks like when concatenated (for context)
    concatenated_text = "".join([item.get('str', '') for item in pdf_text_items[show_start:show_end]])
    
    # Note: The indices shown in the prompt are absolute (starting from 0)
    # The LLM should return absolute indices
    
    # Create prompt for LLM
    prompt = f"""You are helping to match text from a document chunk with text items extracted from a PDF.

CHUNK TEXT (what we're looking for - match THIS EXACTLY):
"{chunk_text}"

IMPORTANT: The PDF text is split into individual items. When concatenated, these items form the full text.
For example, if the chunk text is "June 16, 2025", it might be split across multiple items like:
  [45] 'June'
  [46] '  '  (two spaces)
  [47] '16,'
  [48] ' '
  [49] '202'
  [50] ' '
  [51] '5'

So to match "June 16, 2025", you would return: [45, 46, 47, 48, 49, 50, 51]

PDF TEXT ITEMS (with indices - first 100 items):
{pdf_text_with_indices}

CONCATENATED TEXT (for reference - this is what the items above form when joined):
"{concatenated_text[:300]}"

Your task: Find which PDF text items (by index) contain text that EXACTLY matches the chunk text.
The PDF text may be split differently - numbers and words may be split across multiple items.

CRITICAL REQUIREMENTS:
1. You must match the COMPLETE chunk text, not just part of it
2. If chunk text is "June 16, 2025", find ALL items that together form "June 16, 2025"
3. Do NOT match just "June" if the chunk is "June 16, 2025" - you need the full date
4. The indices you return should form a complete match when concatenated
5. Ignore partial matches - only return indices if they form the complete chunk text
6. Pay attention to how numbers are split - "2025" might be split as "202" and "5"
7. Pay attention to spaces - there might be multiple spaces between words

EXAMPLES:

Example 1: If chunk text is "June 16, 2025" and PDF items are:
  [45] 'June'
  [46] '  '
  [47] '16,'
  [48] ' '
  [49] '202'
  [50] ' '
  [51] '5'
Then return: [45, 46, 47, 48, 49, 50, 51]

Example 2: If chunk text is "Fanuc America Corporation" and PDF items are:
  [59] 'Fanuc'
  [60] ' '
  [61] 'America'
  [62] ' '
  [63] 'Corporation,'
Then return: [59, 60, 61, 62, 63] (include the comma item if it's attached to the word, the normalization will handle it)

IMPORTANT: 
- Look through ALL the PDF items shown above to find where the chunk text appears
- The chunk text might appear anywhere in the items, not just at the beginning
- Include ALL words from the chunk text - if chunk is "Fanuc America Corporation", you need all three words
- Punctuation attached to words (like "Corporation,") should be included - normalization will handle it
- Return the indices in order (lowest to highest)
- Verify: when you concatenate the items at your returned indices, they should form the chunk text (ignoring extra punctuation)

Return ONLY a JSON array of indices that form the complete match, like: [45, 46, 47, 48, 49, 50, 51]
Include ONLY the items needed to form the complete chunk text match.

JSON array only, no other text:"""

    try:
        llm_client = get_llm_client()
        
        # Create a dummy chunk with the prompt
        dummy_chunk = Chunk(
            text=prompt,
            doc_id=document_id,
            clause_number=None,
            page_num=0,
            span_start=0,
            span_end=0,
            source_uri="matching"
        )
        
        result = await llm_client.generate_answer(
            query="Find matching text indices",
            context_chunks=[dummy_chunk],
            citations=[]
        )
        
        print(f"\n=== LLM Response ===")
        print(result.text)
        print("===================\n")
        
        # Extract JSON array from response
        json_match = re.search(r'\[[\d\s,]+\]', result.text)
        if json_match:
            indices = json.loads(json_match.group())
            return indices
        else:
            # Fallback: try to find numbers in response
            numbers = re.findall(r'\d+', result.text)
            indices = [int(n) for n in numbers[:50]]  # Limit to 50 indices
            return indices
            
    except Exception as e:
        print(f"Error in LLM matching: {e}")
        import traceback
        traceback.print_exc()
        return []


def verify_match(chunk_text: str, pdf_items: list, matched_indices: list):
    """Verify that the matched indices actually contain the chunk text."""
    if not matched_indices:
        return False, "No indices returned"
    
    # Get the text from matched indices
    matched_text = ""
    matched_items = []
    for idx in matched_indices:
        if 0 <= idx < len(pdf_items):
            item = pdf_items[idx]
            matched_text += item.get("str", "")
            matched_items.append((idx, item.get("str", "")))
        else:
            return False, f"Index {idx} out of range (max: {len(pdf_items) - 1})"
    
    # Normalize both texts for comparison (remove spaces, commas, hyphens, newlines)
    chunk_normalized = chunk_text.lower().replace(" ", "").replace(",", "").replace("-", "").replace("\n", "")
    matched_normalized = matched_text.lower().replace(" ", "").replace(",", "").replace("-", "").replace("\n", "")
    
    print(f"\n{'='*70}")
    print(f"VISUAL MATCH RESULT")
    print(f"{'='*70}")
    print(f"\nChunk text we're looking for:")
    print(f"  '{chunk_text}'")
    print(f"\nMatched PDF items (indices {matched_indices[0]} to {matched_indices[-1]}):")
    for idx, text in matched_items:
        # Show special characters clearly
        display_text = repr(text) if text.strip() == "" else text
        print(f"  [{idx:3d}] {display_text}")
    print(f"\nMatched text (concatenated):")
    print(f"  '{matched_text}'")
    print(f"\nVisual comparison:")
    print(f"  Chunk:      '{chunk_text}'")
    print(f"  Matched:    '{matched_text}'")
    print(f"  Normalized: '{chunk_normalized}' vs '{matched_normalized}'")
    
    # Show context - what comes before and after
    if matched_indices:
        start_idx = max(0, matched_indices[0] - 5)
        end_idx = min(len(pdf_items), matched_indices[-1] + 6)
        context_items = pdf_items[start_idx:end_idx]
        context_text = "".join([item.get("str", "") for item in context_items])
        
        print(f"\nContext (items {start_idx} to {end_idx}):")
        print(f"  '{context_text}'")
        print(f"\n  {' ' * (matched_indices[0] - start_idx)}{'^' * len(matched_text)} <- MATCHED")
    
    # Match is successful if the matched text contains the chunk text (normalized)
    # The matched text should be equal to or contain the chunk text
    is_match = chunk_normalized == matched_normalized or chunk_normalized in matched_normalized
    print(f"\nMatch result: {'✓ SUCCESS' if is_match else '✗ FAILED'}")
    if not is_match:
        print(f"  Reason: Chunk normalized '{chunk_normalized}' not found in matched normalized '{matched_normalized}'")
    print(f"{'='*70}\n")
    
    return is_match, matched_text


async def main():
    """Main test function."""
    # Use the existing PDF (try both paths)
    pdf_path = "testing/pdf_qa_experiment/fanuc_nda.pdf"
    if not os.path.exists(pdf_path):
        pdf_path = "test_fanuc.pdf"  # Fallback for Docker
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return
    
    print(f"Loading PDF: {pdf_path}")
    
    # Test different extraction methods
    print("\n=== Method 1: Word-level extraction ===")
    pdf_items_words = extract_pdf_text_items_word_level(pdf_path, page_num=0)
    print(f"Extracted {len(pdf_items_words)} text items")
    print("First 30 items:")
    for item in pdf_items_words[:30]:
        print(f"  [{item['index']}] '{item['str']}'")
    
    print("\n=== Method 2: Token-level extraction (simulates PDF.js) ===")
    pdf_items_tokens = extract_pdf_text_items_simulate_pdfjs(pdf_path, page_num=0)
    print(f"Extracted {len(pdf_items_tokens)} text items")
    print("First 50 items:")
    for item in pdf_items_tokens[:50]:
        print(f"  [{item['index']}] '{item['str']}'")
    
    print("\n=== Method 3: Character-level extraction ===")
    pdf_items_chars = extract_pdf_text_items_char_level(pdf_path, page_num=0)
    print(f"Extracted {len(pdf_items_chars)} text items")
    print("First 100 items (showing as string):")
    char_str = "".join([item['str'] for item in pdf_items_chars[:100]])
    print(f"  '{char_str}'")
    
    # Test with various text types from the PDF
    test_texts = [
        # Dates
        "June 16, 2025",
        "June 16",
        "2025",
        # Company names
        "Fanuc America Corporation",
        "Kidde-Fenwal, LLC",
        # Locations
        "Rochester Hills, MI 48309-3253",
        "Ashland, MA 01721",
        # Legal terms
        "Confidential Information",
        "MUTUAL NON-DISCLOSURE AGREEMENT",
        # Phrases
        "entered into as of",
        "reasonable degree of care",
    ]
    
    # Show what the actual text looks like when concatenated
    print("\n=== Full text from token extraction ===")
    full_token_text = "".join([item['str'] for item in pdf_items_tokens])
    print(f"Full text (first 500 chars): {full_token_text[:500]}")
    
    # Find "June 16, 2025" in the text
    print("\n=== Searching for 'June 16, 2025' in extracted text ===")
    search_for = "June 16, 2025"
    # Try different normalizations
    normalized_full = full_token_text.lower().replace(" ", "").replace(",", "")
    normalized_search = search_for.lower().replace(" ", "").replace(",", "")
    
    print(f"Normalized full text contains '{normalized_search}': {normalized_search in normalized_full}")
    
    # Find the actual indices
    # Look for "June" followed by numbers
    june_idx = None
    for i, item in enumerate(pdf_items_tokens):
        if item['str'].lower().strip() == 'june':
            june_idx = i
            print(f"\nFound 'June' at index {i}")
            print(f"Following items:")
            for j in range(i, min(i+10, len(pdf_items_tokens))):
                print(f"  [{pdf_items_tokens[j]['index']}] '{pdf_items_tokens[j]['str']}'")
            break
    
    # Try token-level first (most similar to PDF.js)
    pdf_items = pdf_items_tokens
    
    for test_text in test_texts:
        print(f"\n{'='*60}")
        print(f"Testing with: '{test_text}'")
        print(f"{'='*60}")
        
        # Show what we're searching for in the PDF
        all_text = "".join([item["str"] for item in pdf_items])
        if test_text.lower() in all_text.lower():
            print(f"✓ Text '{test_text}' found in PDF!")
            # Find where it appears
            idx = all_text.lower().find(test_text.lower())
            print(f"  Found at character position: {idx}")
            print(f"  Context: '{all_text[max(0, idx-20):idx+len(test_text)+20]}'")
        else:
            print(f"✗ Text '{test_text}' NOT found in PDF!")
            # Try to find similar text
            print("  Searching for similar text...")
            for i, item in enumerate(pdf_items):
                if test_text.lower().split()[0].lower() in item["str"].lower():
                    print(f"  Found '{test_text.split()[0]}' at index {i}: '{item['str']}'")
                    # Show surrounding items
                    start = max(0, i - 5)
                    end = min(len(pdf_items), i + 10)
                    context = "".join([pdf_items[j]["str"] for j in range(start, end)])
                    print(f"  Context: '{context}'")
                    break
        
        # Test LLM matching
        matched_indices = await test_llm_matching(test_text, pdf_items, "test-doc")
        
        if matched_indices:
            is_valid, matched_text = verify_match(test_text, pdf_items, matched_indices)
            if is_valid:
                print(f"\n{'='*70}")
                print(f"FINAL RESULT: ✓✓✓ SUCCESS! LLM correctly matched '{test_text}'")
                print(f"{'='*70}\n")
            else:
                print(f"\n{'='*70}")
                print(f"FINAL RESULT: ✗✗✗ FAILED! LLM matched incorrectly")
                print(f"   Expected: '{test_text}'")
                print(f"   Got: '{matched_text}'")
                print(f"{'='*70}\n")
        else:
            print(f"\n{'='*70}")
            print(f"FINAL RESULT: ✗✗✗ FAILED! LLM returned no indices")
            print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())

