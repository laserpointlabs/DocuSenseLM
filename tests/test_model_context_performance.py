#!/usr/bin/env python3
"""
Comprehensive test for model size and context window performance
Tests with real PDF documents from data folder
"""

import os
import sys
import time
import json
import subprocess
import statistics
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Try to import parser, fall back to simple extraction
try:
    from ingest.parser import DocumentParser
    PARSER_AVAILABLE = True
except ImportError:
    PARSER_AVAILABLE = False
    print("Warning: DocumentParser not available. Will try to use docker container or install PyPDF2.")

# Test configuration
MODELS = ["llama3.2:1b", "llama3.2:3b"]
CONTEXT_SIZES = [4096, 8192, 16384, 32000]
RESULTS_DIR = Path(__file__).parent / "results"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Test questions about NDA documents
TEST_QUESTIONS = [
    "What is the effective date of this NDA?",
    "What is the expiration date of this NDA?",
    "Who are the parties to this NDA?",
    "What is the governing law for this NDA?",
    "Is this a mutual or unilateral NDA?",
]

def extract_pdf_text(pdf_path: str) -> str:
    """Extract full text from PDF"""
    if PARSER_AVAILABLE:
        parser = DocumentParser()
        result = parser.parse(pdf_path)
        return result.get('text', '')
    else:
        # Try using docker container
        try:
            result = subprocess.run(
                ["docker", "exec", "nda-ingest", "python3", "-c",
                 f"from ingest.parser import DocumentParser; p = DocumentParser(); r = p.parse('{pdf_path}'); print(r.get('text', ''))"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        
        # Fallback: try using API container
        try:
            # Copy PDF to container and extract
            pdf_name = Path(pdf_path).name
            subprocess.run(
                ["docker", "cp", pdf_path, f"nda-api:/tmp/{pdf_name}"],
                check=True,
                capture_output=True
            )
            result = subprocess.run(
                ["docker", "exec", "nda-api", "python3", "-c",
                 f"import sys; sys.path.insert(0, '/app'); from ingest.parser import DocumentParser; p = DocumentParser(); r = p.parse('/tmp/{pdf_name}'); print(r.get('text', ''))"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            print(f"  Could not use API container: {e}")
        
        # Last resort: try installing PyPDF2 with system override
        try:
            import PyPDF2
        except ImportError:
            print("Installing PyPDF2...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--break-system-packages", "PyPDF2"],
                check=True,
                capture_output=True
            )
            import PyPDF2
        
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text_parts = [page.extract_text() for page in pdf_reader.pages]
            return '\n\n'.join(text_parts)

def update_context_length(context_size: int) -> bool:
    """Update OLLAMA_CONTEXT_LENGTH in docker-compose.yml"""
    compose_file = Path(__file__).parent / "docker-compose.yml"
    
    try:
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Replace or add OLLAMA_CONTEXT_LENGTH
        if "OLLAMA_CONTEXT_LENGTH" in content:
            import re
            content = re.sub(
                r'OLLAMA_CONTEXT_LENGTH=\d+',
                f'OLLAMA_CONTEXT_LENGTH={context_size}',
                content
            )
        else:
            # Add after OLLAMA_HOST
            content = content.replace(
                "- OLLAMA_HOST=0.0.0.0",
                f"- OLLAMA_HOST=0.0.0.0\n      - OLLAMA_CONTEXT_LENGTH={context_size}"
            )
        
        with open(compose_file, 'w') as f:
            f.write(content)
        
        # Recreate container
        result = subprocess.run(
            ["docker", "compose", "up", "-d", "--force-recreate", "ollama"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        if result.returncode != 0:
            print(f"Error recreating container: {result.stderr}")
            return False
        
        # Wait for Ollama to be ready
        for i in range(30):
            check = subprocess.run(
                ["docker", "exec", "nda-ollama", "curl", "-s", "http://localhost:11434/api/version"],
                capture_output=True
            )
            if check.returncode == 0:
                time.sleep(2)  # Extra wait for stability
                return True
            time.sleep(1)
        
        return False
    except Exception as e:
        print(f"Error updating context length: {e}")
        return False

def get_gpu_metrics() -> Dict:
    """Get current GPU metrics"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,utilization.gpu,utilization.memory,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if lines:
                parts = lines[0].split(', ')
                return {
                    'gpu_util': float(parts[1]) if len(parts) > 1 else 0,
                    'mem_util': float(parts[2]) if len(parts) > 2 else 0,
                    'mem_used_mib': int(parts[3]) if len(parts) > 3 else 0,
                    'mem_total_mib': int(parts[4]) if len(parts) > 4 else 0,
                }
    except Exception:
        pass
    return {'gpu_util': 0, 'mem_util': 0, 'mem_used_mib': 0, 'mem_total_mib': 0}

def monitor_gpu_during_inference(duration_seconds: float) -> List[Dict]:
    """Monitor GPU metrics during inference"""
    samples = []
    sample_count = max(10, int(duration_seconds * 2))  # Sample every 0.5s, at least 10 samples
    sample_interval = duration_seconds / sample_count if duration_seconds > 0 else 0.1
    
    for _ in range(sample_count):
        metrics = get_gpu_metrics()
        samples.append(metrics)
        time.sleep(sample_interval)
    
    return samples

def run_ollama_query(model: str, context: str, question: str) -> Tuple[str, float, Dict]:
    """Run Ollama query and measure performance"""
    # Build prompt with full document context
    prompt = f"""You are analyzing a Non-Disclosure Agreement (NDA) document.

Here is the complete NDA document:

{context}

Based on the document above, answer this question: {question}

Provide a clear, concise answer. If the information is not in the document, say "I cannot find this information in the provided document"."""

    # Get initial GPU metrics
    initial_gpu = get_gpu_metrics()
    
    # Prepare the query (we'll use the API via curl for better control)
    query_json = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    
    start_time = time.time()
    
    # Start GPU monitoring in background
    import threading
    gpu_samples = []
    monitoring = True
    
    def monitor():
        nonlocal monitoring, gpu_samples
        while monitoring:
            gpu_samples.append(get_gpu_metrics())
            time.sleep(0.2)  # Sample every 200ms
    
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    
    # Run query via API
    result = subprocess.run(
        ["docker", "exec", "nda-ollama", "curl", "-s", "-X", "POST",
         "http://localhost:11434/api/generate",
         "-d", json.dumps(query_json)],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    monitoring = False
    end_time = time.time()
    duration = end_time - start_time
    time.sleep(0.3)  # Let monitoring finish
    
    # Get final GPU metrics
    final_gpu = get_gpu_metrics()
    
    # Parse response
    if result.returncode == 0:
        try:
            response_data = json.loads(result.stdout)
            answer = response_data.get('response', '').strip()
        except json.JSONDecodeError:
            answer = result.stdout.strip()
    else:
        answer = f"ERROR: {result.stderr}"
    
    # Calculate max GPU utilization from samples
    max_gpu_util = max([s['gpu_util'] for s in gpu_samples] + [initial_gpu['gpu_util'], final_gpu['gpu_util']]) if gpu_samples else max(initial_gpu['gpu_util'], final_gpu['gpu_util'])
    avg_gpu_util = statistics.mean([s['gpu_util'] for s in gpu_samples]) if gpu_samples else (initial_gpu['gpu_util'] + final_gpu['gpu_util']) / 2
    
    gpu_metrics = {
        'initial_gpu_util': initial_gpu['gpu_util'],
        'final_gpu_util': final_gpu['gpu_util'],
        'max_gpu_util': max_gpu_util,
        'avg_gpu_util': avg_gpu_util,
        'mem_used_mib': final_gpu['mem_used_mib'] - initial_gpu['mem_used_mib'],
        'mem_total_mib': final_gpu['mem_total_mib'],
        'gpu_samples': len(gpu_samples),
    }
    
    return answer, duration, gpu_metrics

def run_test_combination(model: str, context_size: int, pdf_text: str, pdf_name: str) -> Dict:
    """Run all test questions for a model/context combination"""
    print(f"\n{'='*60}")
    print(f"Testing: {model} with context size {context_size}")
    print(f"Document: {pdf_name}")
    print(f"Document length: {len(pdf_text)} characters (~{len(pdf_text)//4} tokens)")
    print(f"{'='*60}")
    
    # Update context length
    print(f"Updating context length to {context_size}...")
    if not update_context_length(context_size):
        return {"error": "Failed to update context length"}
    
    # Truncate text if needed (rough estimate: 4 chars per token)
    max_chars = context_size * 3  # Leave room for prompt and response
    if len(pdf_text) > max_chars:
        pdf_text = pdf_text[:max_chars]
        print(f"  Truncated document to {len(pdf_text)} characters to fit context window")
    
    results = {
        'model': model,
        'context_size': context_size,
        'pdf_name': pdf_name,
        'document_length_chars': len(pdf_text),
        'document_length_tokens_est': len(pdf_text) // 4,
        'questions': []
    }
    
    # Run each question 3 times for averaging
    for question in TEST_QUESTIONS:
        print(f"\n  Question: {question}")
        times = []
        answers = []
        gpu_utils = []
        mem_usages = []
        
        for run_num in range(3):
            print(f"    Run {run_num + 1}/3...", end=' ', flush=True)
            
            # Unload model between runs to ensure clean state
            subprocess.run(
                ["docker", "exec", "nda-ollama", "ollama", "stop", model],
                capture_output=True
            )
            time.sleep(1)
            
            answer, duration, gpu_metrics = run_ollama_query(model, pdf_text, question)
            
            times.append(duration)
            answers.append(answer)
            gpu_utils.append(gpu_metrics['max_gpu_util'])
            mem_usages.append(gpu_metrics['mem_used_mib'])
            
            print(f"{duration:.2f}s (GPU: {gpu_metrics['max_gpu_util']:.1f}%)")
            time.sleep(2)  # Cool down between runs
        
        # Calculate statistics
        results['questions'].append({
            'question': question,
            'avg_time': statistics.mean(times),
            'min_time': min(times),
            'max_time': max(times),
            'std_time': statistics.stdev(times) if len(times) > 1 else 0,
            'avg_gpu_util': statistics.mean(gpu_utils),
            'max_gpu_util': max(gpu_utils),
            'avg_mem_used': statistics.mean(mem_usages),
            'answers': answers,
            'answer_consistency': len(set(answers)) == 1
        })
    
    return results

def main():
    """Main test execution"""
    print("="*60)
    print("Model Size and Context Window Performance Test")
    print("="*60)
    
    # Find a PDF to test with
    data_dir = Path(__file__).parent / "data"
    pdf_files = list(data_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("Error: No PDF files found in data directory")
        return
    
    # Use the first PDF (or you can specify one)
    test_pdf = pdf_files[0]
    print(f"\nUsing test document: {test_pdf.name}")
    
    # Extract PDF text
    print("Extracting text from PDF...")
    try:
        pdf_text = extract_pdf_text(str(test_pdf))
        print(f"Extracted {len(pdf_text)} characters from PDF")
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return
    
    # Create results directory
    RESULTS_DIR.mkdir(exist_ok=True)
    
    all_results = []
    
    # Test each model and context size combination
    for model in MODELS:
        # Check if model is available
        check = subprocess.run(
            ["docker", "exec", "nda-ollama", "ollama", "list"],
            capture_output=True,
            text=True
        )
        if model not in check.stdout:
            print(f"\n⚠️  Model {model} not found. Skipping...")
            print(f"   Pull it with: docker exec nda-ollama ollama pull {model}")
            continue
        
        for context_size in CONTEXT_SIZES:
            result = run_test_combination(model, context_size, pdf_text, test_pdf.name)
            if 'error' not in result:
                all_results.append(result)
                
                # Save individual result
                result_file = RESULTS_DIR / f"{model.replace(':', '_')}_ctx{context_size}_{TIMESTAMP}.json"
                with open(result_file, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"\n  ✅ Results saved to {result_file}")
    
    # Generate summary
    summary_file = RESULTS_DIR / f"summary_{TIMESTAMP}.txt"
    with open(summary_file, 'w') as f:
        f.write("="*60 + "\n")
        f.write("Model and Context Window Performance Summary\n")
        f.write("="*60 + "\n\n")
        f.write(f"Test Document: {test_pdf.name}\n")
        f.write(f"Document Size: {len(pdf_text)} characters (~{len(pdf_text)//4} tokens)\n")
        f.write(f"Timestamp: {datetime.now()}\n\n")
        
        f.write("Model | Context | Avg Time (s) | GPU Util (%) | Memory (MiB) | Consistency\n")
        f.write("-"*60 + "\n")
        
        for result in all_results:
            model = result['model']
            ctx = result['context_size']
            avg_times = [q['avg_time'] for q in result['questions']]
            avg_gpu = [q['avg_gpu_util'] for q in result['questions']]
            avg_mem = [q['avg_mem_used'] for q in result['questions']]
            consistency = sum(1 for q in result['questions'] if q['answer_consistency'])
            
            f.write(f"{model:15} | {ctx:7} | {statistics.mean(avg_times):11.2f} | "
                   f"{statistics.mean(avg_gpu):11.1f} | {statistics.mean(avg_mem):11.0f} | "
                   f"{consistency}/{len(result['questions'])}\n")
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)
    print(f"\nSummary saved to: {summary_file}")
    print(f"Individual results in: {RESULTS_DIR}")
    print("\nSummary:")
    with open(summary_file, 'r') as f:
        print(f.read())

if __name__ == "__main__":
    main()

