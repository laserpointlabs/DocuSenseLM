#!/usr/bin/env python3
"""Measure response time with full PDF context"""

import requests
import time
import PyPDF2

# Extract PDF text
pdf_file = "data/Norris Cylinder Company_Signed NDA_expires Sept. 2028.pdf"
with open(pdf_file, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    pdf_text = '\n\n'.join([page.extract_text() for page in reader.pages])

print("Testing with full PDF context...")
print("="*60)
print(f"PDF text length: {len(pdf_text)} characters")
print(f"Estimated tokens: ~{len(pdf_text)//4}")

prompt = f"""Document:
{pdf_text}

Question: What is the effective date of this NDA? Answer briefly."""

print(f"Total prompt length: {len(prompt)} characters")
print(f"\nSending request...")

start = time.time()
try:
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2:3b",
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )
    end = time.time()
    duration = end - start
    
    if response.status_code == 200:
        data = response.json()
        answer = data.get('response', '').strip()
        print(f"\n✅ Response received in {duration:.2f} seconds")
        print(f"Answer: {answer[:200]}")
    else:
        print(f"\n❌ Error: {response.status_code}")
        
except Exception as e:
    end = time.time()
    duration = end - start
    print(f"\n❌ Error after {duration:.2f} seconds: {e}")

print(f"\nTotal time: {duration:.2f} seconds")











