#!/usr/bin/env python3
"""
Comprehensive context window performance test
Tests different models, context windows, and corpus sizes
Outputs results for plotting
"""

import requests
import time
import json
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Configuration
MODELS = ["llama3.2:1b", "llama3.2:3b"]
CONTEXT_SIZES = [2048, 4096, 8192, 16384]
API_URL = "http://localhost:11434/api/generate"
RESULTS_DIR = Path(__file__).parent / "results"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Test questions
QUESTIONS = [
    "What is the main topic of this document?",
    "Summarize the key points in 2-3 sentences.",
    "What are the most important details mentioned?",
]

def generate_corpus(size_chars: int) -> str:
    """Generate synthetic corpus of specified size"""
    base_text = """
    This is a comprehensive document about artificial intelligence and machine learning.
    The field of artificial intelligence has evolved significantly over the past decades.
    Machine learning algorithms enable computers to learn from data without explicit programming.
    Deep learning, a subset of machine learning, uses neural networks with multiple layers.
    Natural language processing allows computers to understand and generate human language.
    Computer vision enables machines to interpret and understand visual information.
    Reinforcement learning involves training agents to make decisions through trial and error.
    Transfer learning allows models to apply knowledge from one task to another.
    The development of large language models has revolutionized AI applications.
    Ethical considerations in AI development are increasingly important.
    """
    
    # Repeat and vary to reach target size
    corpus = base_text.strip()
    while len(corpus) < size_chars:
        corpus += "\n\n" + base_text.strip()
    
    # Trim to exact size
    return corpus[:size_chars]

def get_corpus_sizes(context_size: int) -> List[int]:
    """Get corpus sizes to test for a given context window"""
    # Test at 25%, 50%, 75%, and 90% of context window
    # Rough estimate: 4 chars per token
    max_tokens = context_size
    max_chars = max_tokens * 3  # Leave room for prompt and response
    
    sizes = [
        int(max_chars * 0.25),
        int(max_chars * 0.50),
        int(max_chars * 0.75),
        int(max_chars * 0.90),
    ]
    return sizes

def run_inference(model: str, prompt: str, context_size: int) -> Dict:
    """Run inference and measure performance"""
    start = time.time()
    
    try:
        response = requests.post(
            API_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": context_size
                }
            },
            timeout=120
        )
        
        end = time.time()
        duration = end - start
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('response', '').strip()
            
            # Simple confidence metric: length and completeness
            # Longer, more complete answers = higher confidence
            confidence = min(100, len(answer) / 10)  # Rough metric
            
            return {
                "success": True,
                "duration": duration,
                "answer_length": len(answer),
                "confidence": confidence,
                "answer": answer[:200],  # First 200 chars
                "tokens_evaluated": data.get('eval_count', 0),
                "tokens_generated": data.get('prompt_eval_count', 0),
            }
        else:
            return {
                "success": False,
                "duration": duration,
                "error": f"HTTP {response.status_code}",
            }
    except Exception as e:
        end = time.time()
        return {
            "success": False,
            "duration": end - start,
            "error": str(e),
        }

def test_combination(model: str, context_size: int, corpus_size: int, question: str) -> Dict:
    """Test a single combination"""
    corpus = generate_corpus(corpus_size)
    prompt = f"""Document:
{corpus}

Question: {question}

Answer:"""
    
    print(f"    Testing: {len(corpus)} chars, context={context_size}, question='{question[:40]}...'")
    
    # Run 3 times for averaging
    results = []
    for i in range(3):
        result = run_inference(model, prompt, context_size)
        results.append(result)
        time.sleep(1)  # Brief pause between runs
    
    # Calculate averages
    successful = [r for r in results if r.get("success")]
    if not successful:
        return {
            "model": model,
            "context_size": context_size,
            "corpus_size": corpus_size,
            "question": question,
            "success": False,
            "error": "All runs failed"
        }
    
    return {
        "model": model,
        "context_size": context_size,
        "corpus_size": corpus_size,
        "question": question,
        "success": True,
        "avg_duration": statistics.mean([r["duration"] for r in successful]),
        "min_duration": min([r["duration"] for r in successful]),
        "max_duration": max([r["duration"] for r in successful]),
        "avg_confidence": statistics.mean([r.get("confidence", 0) for r in successful]),
        "avg_answer_length": statistics.mean([r.get("answer_length", 0) for r in successful]),
        "runs": len(successful),
        "sample_answer": successful[0].get("answer", "")[:200],
    }

def main():
    """Main test execution"""
    RESULTS_DIR.mkdir(exist_ok=True)
    
    print("="*70)
    print("Context Window Performance Test")
    print("="*70)
    print(f"Models: {', '.join(MODELS)}")
    print(f"Context Sizes: {CONTEXT_SIZES}")
    print(f"Results will be saved to: {RESULTS_DIR}")
    print("="*70)
    print()
    
    all_results = []
    
    for model in MODELS:
        print(f"\n{'='*70}")
        print(f"Testing Model: {model}")
        print(f"{'='*70}")
        
        # Check if model is available
        try:
            check = requests.get(f"http://localhost:11434/api/tags", timeout=5)
            if check.status_code == 200:
                models = [m["name"] for m in check.json().get("models", [])]
                if model not in models:
                    print(f"⚠️  Model {model} not found. Skipping...")
                    print(f"   Pull it with: docker exec nda-ollama ollama pull {model}")
                    continue
        except Exception as e:
            print(f"⚠️  Could not check models: {e}")
            print("   Continuing anyway...")
        
        for context_size in CONTEXT_SIZES:
            print(f"\n  Context Size: {context_size}")
            print(f"  {'-'*68}")
            
            corpus_sizes = get_corpus_sizes(context_size)
            
            for corpus_size in corpus_sizes:
                print(f"\n  Corpus Size: {corpus_size} chars (~{corpus_size//4} tokens)")
                
                for question in QUESTIONS:
                    result = test_combination(model, context_size, corpus_size, question)
                    all_results.append(result)
                    
                    if result.get("success"):
                        print(f"      ✅ {result['avg_duration']:.2f}s, confidence: {result['avg_confidence']:.1f}")
                    else:
                        print(f"      ❌ Failed: {result.get('error', 'Unknown error')}")
    
    # Save results
    json_file = RESULTS_DIR / f"results_{TIMESTAMP}.json"
    csv_file = RESULTS_DIR / f"results_{TIMESTAMP}.csv"
    
    with open(json_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    # Create CSV for easy plotting
    with open(csv_file, 'w') as f:
        f.write("model,context_size,corpus_size,question,avg_duration,min_duration,max_duration,avg_confidence,avg_answer_length,success\n")
        for r in all_results:
            if r.get("success"):
                f.write(f"{r['model']},{r['context_size']},{r['corpus_size']},\"{r['question']}\","
                       f"{r['avg_duration']},{r['min_duration']},{r['max_duration']},"
                       f"{r['avg_confidence']},{r['avg_answer_length']},1\n")
            else:
                f.write(f"{r['model']},{r['context_size']},{r['corpus_size']},\"{r['question']}\","
                       f"0,0,0,0,0,0\n")
    
    print("\n" + "="*70)
    print("Test Complete!")
    print("="*70)
    print(f"\nResults saved to:")
    print(f"  JSON: {json_file}")
    print(f"  CSV:  {csv_file}")
    print(f"\nTotal tests: {len(all_results)}")
    print(f"Successful: {sum(1 for r in all_results if r.get('success'))}")
    print(f"Failed: {sum(1 for r in all_results if not r.get('success'))}")

if __name__ == "__main__":
    main()

