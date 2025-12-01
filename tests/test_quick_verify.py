#!/usr/bin/env python3
"""Quick test to verify the test setup works"""

import requests
import time
from pathlib import Path

API_URL = "http://localhost:11434/api/generate"
RESULTS_DIR = Path(__file__).parent / "results"

print("Quick verification test...")
print("="*60)

# Test 1: Check API is accessible
print("1. Checking Ollama API...")
try:
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    if response.status_code == 200:
        models = [m["name"] for m in response.json().get("models", [])]
        print(f"   ✅ API accessible, found {len(models)} models")
        if "llama3.2:1b" in models:
            print("   ✅ llama3.2:1b available")
        if "llama3.2:3b" in models:
            print("   ✅ llama3.2:3b available")
    else:
        print(f"   ❌ API returned {response.status_code}")
        exit(1)
except Exception as e:
    print(f"   ❌ Cannot connect to API: {e}")
    exit(1)

# Test 2: Check results directory
print("\n2. Checking results directory...")
RESULTS_DIR.mkdir(exist_ok=True)
if RESULTS_DIR.exists():
    print(f"   ✅ Results directory: {RESULTS_DIR}")
else:
    print(f"   ❌ Cannot create results directory")
    exit(1)

# Test 3: Run a simple inference
print("\n3. Testing simple inference...")
start = time.time()
try:
    response = requests.post(
        API_URL,
        json={
            "model": "llama3.2:1b",
            "prompt": "What is 2+2? Answer with just the number.",
            "stream": False
        },
        timeout=30
    )
    duration = time.time() - start
    
    if response.status_code == 200:
        data = response.json()
        answer = data.get('response', '').strip()
        print(f"   ✅ Inference successful in {duration:.2f}s")
        print(f"   Answer: {answer}")
    else:
        print(f"   ❌ Inference failed: {response.status_code}")
        exit(1)
except Exception as e:
    print(f"   ❌ Inference error: {e}")
    exit(1)

print("\n" + "="*60)
print("✅ All checks passed! Ready to run full test.")
print("="*60)



















