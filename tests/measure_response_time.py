#!/usr/bin/env python3
"""Measure actual response time from Ollama"""

import requests
import time

api_url = "http://localhost:11434/api/generate"

# Simple test
print("Testing response time...")
print("="*60)

query = {
    "model": "llama3.2:3b",
    "prompt": "What is 2+2? Answer with just the number.",
    "stream": False
}

print(f"Model: llama3.2:3b")
print(f"Prompt: {query['prompt']}")
print(f"\nSending request...")

start = time.time()
try:
    response = requests.post(api_url, json=query, timeout=60)
    end = time.time()
    
    duration = end - start
    
    if response.status_code == 200:
        data = response.json()
        answer = data.get('response', '').strip()
        print(f"\n✅ Response received in {duration:.2f} seconds")
        print(f"Answer: {answer}")
        print(f"Answer length: {len(answer)} characters")
    else:
        print(f"\n❌ Error: {response.status_code}")
        print(response.text[:200])
        
except Exception as e:
    end = time.time()
    duration = end - start
    print(f"\n❌ Error after {duration:.2f} seconds: {e}")

print(f"\nTotal time: {duration:.2f} seconds")





















