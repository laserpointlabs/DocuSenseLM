#!/usr/bin/env python3
"""
Q&A Evaluation Script
Tests LLM's ability to answer questions about PDF content
Evaluates confidence and accuracy against expected data
Tests both 1b and 3b models
"""

import requests
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# Configuration
PDF_TEXT_FILE = Path(__file__).parent / "extracted_text.txt"
EXPECTED_DATA_FILE = Path(__file__).parent / "expected_data.json"
API_URL = "http://localhost:11434/api/generate"
MODELS = ["llama3.2:1b", "llama3.2:3b"]  # Test both models
CONTEXT_WINDOW = 16384
RESULTS_DIR = Path(__file__).parent / "results"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Test questions based on ontology
TEST_QUESTIONS = [
    {
        "id": "q1",
        "question": "What is the effective date of this NDA?",
        "expected_field": "effective_date",
        "expected_value": "2025-06-16",
        "category": "metadata"
    },
    {
        "id": "q2",
        "question": "What is the expiration date of this NDA?",
        "expected_field": "expiration_date",
        "expected_value": "2028-06-16",
        "category": "metadata"
    },
    {
        "id": "q3",
        "question": "Who are the parties to this NDA?",
        "expected_field": "parties",
        "expected_value": ["Fanuc America Corporation", "Kidde-Fenwal, LLC"],
        "category": "parties"
    },
    {
        "id": "q4",
        "question": "Is this a mutual or unilateral NDA?",
        "expected_field": "is_mutual",
        "expected_value": True,
        "category": "metadata"
    },
    {
        "id": "q5",
        "question": "What is the term or duration of this NDA in months?",
        "expected_field": "term_months",
        "expected_value": 36,
        "category": "term"
    },
    {
        "id": "q6",
        "question": "What is the governing law for this NDA?",
        "expected_field": "governing_law",
        "expected_value": "State of California",
        "category": "metadata"
    },
    {
        "id": "q7",
        "question": "What is the address of Fanuc America Corporation?",
        "expected_field": "parties",
        "expected_value": "3900 West Hamlin Road, Rochester Hills, MI 48309-3253, USA",
        "category": "parties"
    },
    {
        "id": "q8",
        "question": "What is the address of Kidde-Fenwal, LLC?",
        "expected_field": "parties",
        "expected_value": "400 Main Street, Ashland, MA 01721, USA",
        "category": "parties"
    },
    {
        "id": "q9",
        "question": "What is the confidentiality period or term of this agreement?",
        "expected_field": "term_months",
        "expected_value": 36,
        "category": "term"
    },
    {
        "id": "q10",
        "question": "When does this NDA expire?",
        "expected_field": "expiration_date",
        "expected_value": "2028-06-16",
        "category": "metadata"
    }
]

def load_pdf_text() -> str:
    """Load extracted PDF text"""
    with open(PDF_TEXT_FILE, 'r') as f:
        return f.read()

def load_expected_data() -> dict:
    """Load expected data structure"""
    with open(EXPECTED_DATA_FILE, 'r') as f:
        return json.load(f)

def ask_llm(question: str, pdf_text: str, model: str) -> Tuple[str, float, dict]:
    """Ask LLM a question with full PDF context"""
    prompt = f"""You are analyzing a Non-Disclosure Agreement (NDA) document.

Here is the complete NDA document:

{pdf_text}

Based on the document above, answer this question: {question}

Provide a clear, concise answer. If the information is not in the document, say "I cannot find this information in the provided document"."""

    start_time = time.time()
    
    try:
        response = requests.post(
            API_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": CONTEXT_WINDOW
                }
            },
            timeout=120
        )
        
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('response', '').strip()
            
            # Simple confidence metric based on answer length and completeness
            confidence = min(100, len(answer) / 10) if answer else 0
            
            return answer, duration, {
                "success": True,
                "confidence": confidence,
                "answer_length": len(answer),
                "tokens_evaluated": data.get('eval_count', 0),
                "tokens_generated": data.get('prompt_eval_count', 0)
            }
        else:
            return f"ERROR: HTTP {response.status_code}", duration, {"success": False}
            
    except Exception as e:
        duration = time.time() - start_time
        return f"ERROR: {str(e)}", duration, {"success": False}

def evaluate_answer(answer: str, expected: any, question_type: str) -> dict:
    """Evaluate answer against expected value"""
    answer_lower = answer.lower()
    
    # Simple evaluation - can be enhanced
    if expected is None:
        # Check if answer indicates "not found"
        if "cannot find" in answer_lower or "not in" in answer_lower or "not found" in answer_lower:
            return {"correct": True, "match_score": 1.0, "reason": "Correctly identified as not in document"}
        else:
            return {"correct": False, "match_score": 0.0, "reason": "Should indicate not found"}
    
    if question_type == "date":
        # Extract dates from answer - be flexible with formats
        import re
        from datetime import datetime
        
        # Try to parse expected date
        try:
            if isinstance(expected, str):
                expected_date = datetime.strptime(expected, "%Y-%m-%d")
            else:
                expected_date = expected
        except:
            expected_date = None
        
        # Extract dates from answer (various formats)
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{1,2}[/-]\d{1,2}[/-]\d{4}',  # MM/DD/YYYY or MM-DD-YYYY
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2}',  # MM/DD/YY
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',  # Month DD, YYYY
        ]
        
        found_dates = []
        for pattern in date_patterns:
            found_dates.extend(re.findall(pattern, answer))
        
        # Also check for year mentions
        years = re.findall(r'\b(20\d{2})\b', answer)
        
        if expected_date:
            expected_year = expected_date.year
            expected_month = expected_date.month
            expected_day = expected_date.day
            
            # Check if year matches
            if str(expected_year) in years:
                return {"correct": True, "match_score": 0.8, "reason": f"Year {expected_year} matches"}
            
            # Try to parse found dates
            for date_str in found_dates:
                try:
                    # Try different formats
                    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%B %d %Y"]:
                        try:
                            parsed = datetime.strptime(date_str, fmt)
                            if parsed.year == expected_year and parsed.month == expected_month and parsed.day == expected_day:
                                return {"correct": True, "match_score": 1.0, "reason": "Date matches exactly"}
                            elif parsed.year == expected_year and parsed.month == expected_month:
                                return {"correct": True, "match_score": 0.9, "reason": "Year and month match"}
                            elif parsed.year == expected_year:
                                return {"correct": True, "match_score": 0.8, "reason": f"Year {expected_year} matches"}
                        except:
                            continue
                except:
                    continue
        
        # Check if expected date components are mentioned
        if expected_date:
            if str(expected_date.year) in answer and str(expected_date.month) in answer:
                return {"correct": True, "match_score": 0.7, "reason": "Year and month mentioned"}
            elif str(expected_date.year) in answer:
                return {"correct": True, "match_score": 0.6, "reason": f"Year {expected_date.year} mentioned"}
        
        return {"correct": False, "match_score": 0.0, "reason": "Date does not match"}
    
    elif question_type == "parties":
        # Check if party names are mentioned
        if isinstance(expected, list):
            found = sum(1 for party in expected if party.lower() in answer_lower)
            score = found / len(expected) if expected else 0
            return {"correct": score > 0.5, "match_score": score, "reason": f"Found {found}/{len(expected)} parties"}
        else:
            # Single value (like address) - be flexible with formatting
            expected_lower = expected.lower()
            
            # Remove common punctuation and normalize whitespace
            import re
            expected_clean = re.sub(r'[,\s]+', ' ', expected_lower).strip()
            answer_clean = re.sub(r'[,\s]+', ' ', answer_lower).strip()
            
            # Check for exact match
            if expected_lower in answer_lower:
                return {"correct": True, "match_score": 1.0, "reason": "Value found in answer"}
            
            # Check for normalized match
            if expected_clean in answer_clean:
                return {"correct": True, "match_score": 0.9, "reason": "Value found (normalized)"}
            
            # Check for key components (for addresses)
            expected_parts = expected_clean.split()
            if len(expected_parts) > 3:
                # For addresses, check if most parts match
                matching_parts = sum(1 for part in expected_parts if len(part) > 3 and part in answer_clean)
                if matching_parts >= len(expected_parts) * 0.7:  # 70% of parts match
                    return {"correct": True, "match_score": 0.8, "reason": f"Most address components match ({matching_parts}/{len(expected_parts)})"}
            
            return {"correct": False, "match_score": 0.0, "reason": "Value not found"}
    
    elif question_type == "boolean":
        # Check for mutual/unilateral
        if expected is True:
            if "mutual" in answer_lower:
                return {"correct": True, "match_score": 1.0, "reason": "Correctly identified as mutual"}
        elif expected is False:
            if "unilateral" in answer_lower:
                return {"correct": True, "match_score": 1.0, "reason": "Correctly identified as unilateral"}
        return {"correct": False, "match_score": 0.0, "reason": "Boolean value mismatch"}
    
    elif question_type == "number":
        # Extract numbers from answer - look for years/months context
        import re
        
        # Look for "X years" or "X months" patterns
        year_pattern = r'(\d+)\s+years?'
        month_pattern = r'(\d+)\s+months?'
        
        years = re.findall(year_pattern, answer, re.IGNORECASE)
        months = re.findall(month_pattern, answer, re.IGNORECASE)
        
        # If looking for months and found years, convert
        if months:
            try:
                answer_num = int(months[0])
                if answer_num == expected:
                    return {"correct": True, "match_score": 1.0, "reason": "Number of months matches"}
            except:
                pass
        
        if years:
            try:
                years_num = int(years[0])
                months_from_years = years_num * 12
                if months_from_years == expected:
                    return {"correct": True, "match_score": 1.0, "reason": f"Found {years_num} years = {expected} months"}
                elif abs(months_from_years - expected) <= 1:
                    return {"correct": True, "match_score": 0.9, "reason": f"Close match: {years_num} years ≈ {expected} months"}
            except:
                pass
        
        # Fallback: extract any numbers
        numbers = re.findall(r'\b\d+\b', answer)
        if numbers:
            try:
                # Check all numbers found
                for num_str in numbers:
                    answer_num = int(num_str)
                    if answer_num == expected:
                        return {"correct": True, "match_score": 1.0, "reason": "Number matches"}
                    elif answer_num * 12 == expected:  # Years to months
                        return {"correct": True, "match_score": 1.0, "reason": f"Found {answer_num} years = {expected} months"}
            except:
                pass
        
        return {"correct": False, "match_score": 0.0, "reason": "Could not extract matching number"}
    
    # Default: simple string matching
    expected_str = str(expected).lower()
    if expected_str in answer_lower:
        return {"correct": True, "match_score": 1.0, "reason": "Value found in answer"}
    else:
        return {"correct": False, "match_score": 0.0, "reason": "Value not found in answer"}

def generate_report(all_results: List[dict], timestamp: str) -> str:
    """Generate a readable text report"""
    report = []
    report.append("="*80)
    report.append("PDF Q&A Evaluation Report")
    report.append("="*80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"PDF: {PDF_TEXT_FILE.name}")
    report.append(f"Context Window: {CONTEXT_WINDOW} tokens")
    report.append("")
    
    # Overall summary
    report.append("EXECUTIVE SUMMARY")
    report.append("-"*80)
    
    for model in MODELS:
        model_data = [r for r in all_results if r['model'] == model]
        if not model_data:
            continue
            
        correct = sum(1 for r in model_data if r['correct'])
        total = len(model_data)
        avg_score = sum(r['match_score'] for r in model_data) / total
        avg_duration = sum(r['duration'] for r in model_data) / total
        avg_confidence = sum(r['confidence'] for r in model_data) / total
        
        report.append(f"\n{model}:")
        report.append(f"  Accuracy: {correct}/{total} ({correct/total*100:.1f}%)")
        report.append(f"  Average Match Score: {avg_score:.2f}")
        report.append(f"  Average Response Time: {avg_duration:.2f} seconds")
        report.append(f"  Average Confidence: {avg_confidence:.1f}")
    
    report.append("")
    report.append("="*80)
    report.append("DETAILED RESULTS")
    report.append("="*80)
    report.append("")
    
    # Group by question
    for qa in TEST_QUESTIONS:
        report.append(f"Question {qa['id']}: {qa['question']}")
        report.append(f"Category: {qa['category']}")
        report.append(f"Expected: {qa['expected_value']}")
        report.append("-"*80)
        
        for model in MODELS:
            model_results = [r for r in all_results if r['model'] == model and r['question_id'] == qa['id']]
            if not model_results:
                continue
                
            result = model_results[0]
            status = "✓ CORRECT" if result['correct'] else "✗ INCORRECT"
            
            report.append(f"\n{model}:")
            report.append(f"  Status: {status}")
            report.append(f"  Match Score: {result['match_score']:.2f}")
            report.append(f"  Response Time: {result['duration']:.2f}s")
            report.append(f"  Confidence: {result['confidence']:.1f}")
            report.append(f"  Evaluation: {result['evaluation_reason']}")
            report.append(f"  Answer: {result['answer'][:200]}")
            if len(result['answer']) > 200:
                report.append(f"           ... (truncated, full length: {result['answer_length']} chars)")
        
        report.append("")
        report.append("")
    
    # Model comparison
    report.append("="*80)
    report.append("MODEL COMPARISON")
    report.append("="*80)
    report.append("")
    
    comparison_data = []
    for model in MODELS:
        model_data = [r for r in all_results if r['model'] == model]
        if not model_data:
            continue
            
        correct = sum(1 for r in model_data if r['correct'])
        total = len(model_data)
        avg_score = sum(r['match_score'] for r in model_data) / total
        avg_duration = sum(r['duration'] for r in model_data) / total
        
        comparison_data.append({
            'model': model,
            'accuracy': correct/total*100,
            'score': avg_score,
            'time': avg_duration
        })
    
    if len(comparison_data) == 2:
        report.append("Performance Comparison:")
        report.append(f"  Accuracy: {comparison_data[0]['model']} = {comparison_data[0]['accuracy']:.1f}% vs "
                      f"{comparison_data[1]['model']} = {comparison_data[1]['accuracy']:.1f}%")
        report.append(f"  Speed: {comparison_data[0]['model']} = {comparison_data[0]['time']:.2f}s vs "
                      f"{comparison_data[1]['model']} = {comparison_data[1]['time']:.2f}s")
        
        if comparison_data[0]['time'] < comparison_data[1]['time']:
            report.append(f"  → {comparison_data[0]['model']} is {comparison_data[1]['time']/comparison_data[0]['time']:.1f}x faster")
        else:
            report.append(f"  → {comparison_data[1]['model']} is {comparison_data[0]['time']/comparison_data[1]['time']:.1f}x faster")
        
        if comparison_data[0]['accuracy'] > comparison_data[1]['accuracy']:
            report.append(f"  → {comparison_data[0]['model']} has {comparison_data[0]['accuracy'] - comparison_data[1]['accuracy']:.1f}% higher accuracy")
        elif comparison_data[1]['accuracy'] > comparison_data[0]['accuracy']:
            report.append(f"  → {comparison_data[1]['model']} has {comparison_data[1]['accuracy'] - comparison_data[0]['accuracy']:.1f}% higher accuracy")
        else:
            report.append(f"  → Both models have equal accuracy")
    
    report.append("")
    report.append("="*80)
    report.append("END OF REPORT")
    report.append("="*80)
    
    return "\n".join(report)

def main():
    print("="*70)
    print("PDF Q&A Evaluation - Multi-Model Comparison")
    print("="*70)
    print(f"Models: {', '.join(MODELS)}")
    print(f"Context Window: {CONTEXT_WINDOW}")
    print(f"PDF: {PDF_TEXT_FILE.name}")
    print("="*70)
    print()
    
    # Load data
    pdf_text = load_pdf_text()
    expected_data = load_expected_data()
    
    print(f"PDF Text: {len(pdf_text):,} characters (~{len(pdf_text)//4:,} tokens)")
    print(f"Questions to test: {len(TEST_QUESTIONS)}")
    print()
    
    RESULTS_DIR.mkdir(exist_ok=True)
    
    all_results = []
    
    for model in MODELS:
        print(f"\n{'='*70}")
        print(f"Testing Model: {model}")
        print(f"{'='*70}")
        print()
        
        for i, qa in enumerate(TEST_QUESTIONS, 1):
            print(f"[{i}/{len(TEST_QUESTIONS)}] {qa['question']}")
            print(f"  Expected: {qa['expected_value']}")
            
            # Ask LLM
            answer, duration, metrics = ask_llm(qa['question'], pdf_text, model)
            
            # Determine question type
            if qa['expected_field'] in ['effective_date', 'expiration_date']:
                q_type = "date"
            elif qa['expected_field'] == 'parties':
                q_type = "parties"
            elif qa['expected_field'] == 'is_mutual':
                q_type = "boolean"
            elif qa['expected_field'] in ['term_months', 'survival_months']:
                q_type = "number"
            else:
                q_type = "string"
            
            # Evaluate
            evaluation = evaluate_answer(answer, qa['expected_value'], q_type)
            
            result = {
                "model": model,
                "question_id": qa['id'],
                "question": qa['question'],
                "category": qa['category'],
                "expected_field": qa['expected_field'],
                "expected_value": qa['expected_value'],
                "answer": answer,
                "duration": duration,
                "correct": evaluation['correct'],
                "match_score": evaluation['match_score'],
                "evaluation_reason": evaluation['reason'],
                "confidence": metrics.get('confidence', 0),
                "answer_length": metrics.get('answer_length', 0),
                **metrics
            }
            
            all_results.append(result)
            
            status = "✅" if evaluation['correct'] else "❌"
            print(f"  Answer: {answer[:100]}...")
            print(f"  {status} Correct: {evaluation['correct']} | Score: {evaluation['match_score']:.2f} | Time: {duration:.2f}s")
            print(f"  Reason: {evaluation['reason']}")
            print()
            
            time.sleep(1)  # Brief pause between questions
        
        # Model summary
        model_data = [r for r in all_results if r['model'] == model]
        correct = sum(1 for r in model_data if r['correct'])
        avg_score = sum(r['match_score'] for r in model_data) / len(model_data)
        avg_duration = sum(r['duration'] for r in model_data) / len(model_data)
        avg_confidence = sum(r['confidence'] for r in model_data) / len(model_data)
        
        print(f"  {model} Summary:")
        print(f"    Correct: {correct}/{len(model_data)} ({correct/len(model_data)*100:.1f}%)")
        print(f"    Avg Score: {avg_score:.2f}")
        print(f"    Avg Time: {avg_duration:.2f}s")
        print(f"    Avg Confidence: {avg_confidence:.1f}")
        print()
    
    # Save results
    json_file = RESULTS_DIR / f"qa_results_{TIMESTAMP}.json"
    csv_file = RESULTS_DIR / f"qa_results_{TIMESTAMP}.csv"
    report_file = RESULTS_DIR / f"qa_report_{TIMESTAMP}.txt"
    
    with open(json_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    # Create CSV
    import csv
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'model', 'question_id', 'question', 'category', 'expected_value', 'answer',
            'correct', 'match_score', 'duration', 'confidence', 'evaluation_reason'
        ])
        writer.writeheader()
        for r in all_results:
            writer.writerow({
                'model': r['model'],
                'question_id': r['question_id'],
                'question': r['question'],
                'category': r['category'],
                'expected_value': str(r['expected_value']),
                'answer': r['answer'][:200],  # Truncate long answers
                'correct': r['correct'],
                'match_score': r['match_score'],
                'duration': r['duration'],
                'confidence': r['confidence'],
                'evaluation_reason': r['evaluation_reason']
            })
    
    # Generate report
    report_text = generate_report(all_results, TIMESTAMP)
    with open(report_file, 'w') as f:
        f.write(report_text)
    
    # Overall Summary
    print("="*70)
    print("Overall Evaluation Summary")
    print("="*70)
    
    for model in MODELS:
        model_data = [r for r in all_results if r['model'] == model]
        if not model_data:
            continue
        correct = sum(1 for r in model_data if r['correct'])
        avg_score = sum(r['match_score'] for r in model_data) / len(model_data)
        avg_duration = sum(r['duration'] for r in model_data) / len(model_data)
        avg_confidence = sum(r['confidence'] for r in model_data) / len(model_data)
        
        print(f"\n{model}:")
        print(f"  Correct: {correct}/{len(model_data)} ({correct/len(model_data)*100:.1f}%)")
        print(f"  Avg Score: {avg_score:.2f}")
        print(f"  Avg Time: {avg_duration:.2f}s")
        print(f"  Avg Confidence: {avg_confidence:.1f}")
    
    print()
    print(f"Results saved to:")
    print(f"  JSON: {json_file}")
    print(f"  CSV:  {csv_file}")
    print(f"  Report: {report_file}")
    print("="*70)

if __name__ == "__main__":
    main()
