#!/usr/bin/env python3
"""
Estimate context window requirements for PDF files in data folder
"""

import PyPDF2
from pathlib import Path
import sys

def estimate_pdf_tokens(pdf_path: Path) -> dict:
    """Extract text and estimate token count"""
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text_parts = [page.extract_text() for page in reader.pages]
            full_text = '\n\n'.join(text_parts)
            
            # Token estimation: ~4 characters per token (conservative)
            tokens_est = len(full_text) // 4
            
            # Add buffer for prompt and response (typically 500-1000 tokens)
            buffer = 1000
            recommended_context = tokens_est + buffer
            
            return {
                'pages': len(reader.pages),
                'characters': len(full_text),
                'words': len(full_text.split()),
                'tokens_est': tokens_est,
                'recommended_context': recommended_context,
                'fits_4096': tokens_est < 4096,
                'fits_8192': tokens_est < 8192,
                'fits_16384': tokens_est < 16384,
            }
    except Exception as e:
        return {'error': str(e)}

def main():
    data_dir = Path(__file__).parent.parent.parent / "data"
    pdfs = sorted(data_dir.glob("*.pdf"))
    
    if not pdfs:
        print("No PDF files found in data folder")
        return
    
    print("="*80)
    print("PDF Context Window Requirements Analysis")
    print("="*80)
    print()
    
    results = []
    
    for pdf_file in pdfs:
        print(f"Analyzing: {pdf_file.name}")
        result = estimate_pdf_tokens(pdf_file)
        
        if 'error' in result:
            print(f"  ❌ Error: {result['error']}\n")
            continue
        
        results.append({
            'file': pdf_file.name,
            **result
        })
        
        print(f"  Pages: {result['pages']}")
        print(f"  Characters: {result['characters']:,}")
        print(f"  Words: {result['words']:,}")
        print(f"  Estimated tokens: ~{result['tokens_est']:,}")
        print(f"  Recommended context: {result['recommended_context']:,} tokens")
        print(f"  Fits in 4096: {'✅ Yes' if result['fits_4096'] else '❌ No'}")
        print(f"  Fits in 8192: {'✅ Yes' if result['fits_8192'] else '❌ No'}")
        print(f"  Fits in 16384: {'✅ Yes' if result['fits_16384'] else '❌ No'}")
        print()
    
    # Summary
    print("="*80)
    print("Summary")
    print("="*80)
    
    if results:
        avg_tokens = sum(r['tokens_est'] for r in results) / len(results)
        max_tokens = max(r['tokens_est'] for r in results)
        min_tokens = min(r['tokens_est'] for r in results)
        
        print(f"Total PDFs analyzed: {len(results)}")
        print(f"Average tokens per PDF: ~{avg_tokens:,.0f}")
        print(f"Smallest PDF: ~{min_tokens:,} tokens")
        print(f"Largest PDF: ~{max_tokens:,} tokens")
        print()
        
        print("Context Window Recommendations:")
        print(f"  - For smallest PDFs: {min_tokens + 1000:,} tokens")
        print(f"  - For average PDFs: {avg_tokens + 1000:,.0f} tokens")
        print(f"  - For largest PDFs: {max_tokens + 1000:,} tokens")
        print()
        
        print("Current Settings:")
        print(f"  - Current context (4096): {'✅ Covers most' if avg_tokens < 3500 else '⚠️ May be tight'}")
        print(f"  - 8192 context: {'✅ Comfortable' if max_tokens < 7000 else '⚠️ May need more'}")
        print(f"  - 16384 context: ✅ Should cover all PDFs")
        print()
        
        print("Recommendation for Full PDF Chat:")
        if max_tokens < 7000:
            print("  ✅ 8192 token context window is sufficient for full PDF chat")
        elif max_tokens < 15000:
            print("  ✅ 16384 token context window recommended for full PDF chat")
        else:
            print("  ⚠️ Some PDFs may exceed 16384 tokens - consider chunking or larger context")

if __name__ == "__main__":
    main()











