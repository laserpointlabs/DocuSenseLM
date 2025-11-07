#!/usr/bin/env python3
"""
Generate document-specific test questions based on actual PDF content
Each question is tied to a specific document and asks about real information from that document
"""
import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from api.db import get_db_session
from api.db.schema import Document, DocumentMetadata, Party, DocumentChunk, DocumentStatus


def extract_company_name_from_filename(filename: str) -> str:
    """Extract company name from filename"""
    # Remove common suffixes and extensions
    name = filename.replace('_Signed NDA_Expires', '').replace('.pdf', '')
    # Remove date suffixes
    name = name.rsplit('_', 1)[0] if '_' in name else name
    return name.strip()


def get_document_specific_info() -> List[Dict[str, Any]]:
    """Get all document-specific information from database"""
    db = get_db_session()
    try:
        docs = db.query(Document).filter(Document.status == DocumentStatus.PROCESSED).all()
        
        doc_info = []
        for doc in docs:
            info = {
                'filename': doc.filename,
                'doc_id': str(doc.id),
                'company_name': extract_company_name_from_filename(doc.filename)
            }
            
            # Get metadata
            metadata = db.query(DocumentMetadata).filter(
                DocumentMetadata.document_id == doc.id
            ).first()
            
            if metadata:
                info['effective_date'] = str(metadata.effective_date) if metadata.effective_date else None
                info['governing_law'] = metadata.governing_law
                info['term_months'] = metadata.term_months
                info['is_mutual'] = metadata.is_mutual
                info['survival_months'] = metadata.survival_months
                
                # Calculate expiration date
                if metadata.effective_date and metadata.term_months:
                    from dateutil.relativedelta import relativedelta
                    expiration = metadata.effective_date + relativedelta(months=metadata.term_months)
                    info['expiration_date'] = str(expiration)
            
            # Get parties
            parties = db.query(Party).filter(Party.document_id == doc.id).all()
            info['parties'] = []
            for p in parties:
                party_info = {
                    'name': p.party_name,
                    'address': p.address,
                    'type': p.party_type
                }
                info['parties'].append(party_info)
            
            # Get sample chunks to find specific details (addresses, signatures, etc.)
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id
            ).limit(20).all()
            
            # Look for addresses in chunks
            addresses_found = set()
            for chunk in chunks:
                text = chunk.text.lower()
                # Look for address patterns
                if 'corporate office' in text or 'headquarters' in text or 'head office' in text:
                    # Extract surrounding text
                    lines = chunk.text.split('\n')
                    for i, line in enumerate(lines):
                        if 'corporate office' in line.lower() or 'headquarters' in line.lower():
                            # Get next few lines as potential address
                            address_lines = []
                            for j in range(i, min(i+5, len(lines))):
                                if lines[j].strip():
                                    address_lines.append(lines[j].strip())
                            if address_lines:
                                addresses_found.add(' '.join(address_lines[:3]))
            
            info['addresses_found'] = list(addresses_found)[:2]  # Limit to 2 addresses
            
            doc_info.append(info)
        
        return doc_info
    finally:
        db.close()


def introduce_misspellings(text: str, severity: str = "medium") -> str:
    """Introduce realistic misspellings into text
    
    Args:
        text: Text to misspell
        severity: "light" (1-2 chars), "medium" (2-3 chars), "heavy" (3+ chars)
    """
    import random
    
    # Common misspelling patterns
    misspellings = {
        'effective': ['effecive', 'efective', 'effetive'],
        'governing': ['govering', 'governing', 'governing'],
        'expiration': ['expiraton', 'expiration', 'expiratin'],
        'distribution': ['distributon', 'distribtion', 'distributin'],
        'corporation': ['corperation', 'corporaton', 'corperaton'],
        'company': ['comapny', 'compnay', 'comany'],
        'located': ['locatd', 'locate', 'locatd'],
        'parties': ['partys', 'partes', 'partis'],
        'mutual': ['mutul', 'mutal', 'mutua'],
        'agreement': ['agreemnt', 'agreemet', 'agreemnt'],
        'date': ['dte', 'dat', 'dte'],
        'state': ['stat', 'stae', 'stat'],
        'law': ['lw', 'la', 'lw'],
    }
    
    result = text
    words = text.split()
    num_changes = 1 if severity == "light" else (2 if severity == "medium" else 3)
    
    for _ in range(min(num_changes, len(words))):
        word_idx = random.randint(0, len(words) - 1)
        word_lower = words[word_idx].lower().rstrip('?.,!')
        
        # Check if we have a misspelling for this word
        if word_lower in misspellings:
            misspelled = random.choice(misspellings[word_lower])
            # Preserve capitalization and punctuation
            if words[word_idx][0].isupper():
                misspelled = misspelled.capitalize()
            if words[word_idx].endswith('?'):
                misspelled += '?'
            elif words[word_idx].endswith('.'):
                misspelled += '.'
            elif words[word_idx].endswith(','):
                misspelled += ','
            words[word_idx] = misspelled
    
    return ' '.join(words)


def generate_question_variations(base_question: str, category: str, doc_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate 2 variations of a question: one natural rephrasing and one with misspellings
    
    Returns:
        List of dicts with 'question', 'confidence', 'has_misspelling' keys
    """
    company_name = doc_info['company_name']
    variations = []
    
    # Variation 1: Natural rephrasing (higher confidence)
    natural_variation = None
    
    if category == "Governing Law":
        if "governing state" in base_question.lower():
            natural_variation = base_question.replace("governing state", "governing law")
        elif "governing law" in base_question.lower():
            natural_variation = base_question.replace("governing law", "governing state")
        else:
            natural_variation = base_question.replace("What is the governing", "Which state's laws govern")
    
    elif category == "Effective Date":
        if "become effective" in base_question.lower():
            natural_variation = base_question.replace("become effective", "take effect")
        elif "take effect" in base_question.lower():
            natural_variation = base_question.replace("take effect", "become effective")
        else:
            natural_variation = base_question.replace("When did", "On what date did")
    
    elif category == "Expiration Date":
        if "expire" in base_question.lower():
            natural_variation = base_question.replace("expire", "end")
        elif "end" in base_question.lower():
            natural_variation = base_question.replace("end", "expire")
        else:
            natural_variation = base_question.replace("What date does", "When will")
    
    elif category == "Term":
        if "term" in base_question.lower():
            natural_variation = base_question.replace("term", "duration")
        elif "duration" in base_question.lower():
            natural_variation = base_question.replace("duration", "term")
        else:
            natural_variation = base_question.replace("What is the term", "How long is")
    
    elif category == "Parties":
        if "parties" in base_question.lower():
            natural_variation = base_question.replace("parties to", "signatories of")
        elif "signatories" in base_question.lower():
            natural_variation = base_question.replace("signatories", "parties")
        else:
            natural_variation = base_question.replace("Who are the parties", "Which companies are parties")
    
    elif category == "Location":
        if "located" in base_question.lower():
            natural_variation = base_question.replace("located", "headquartered")
        elif "headquartered" in base_question.lower():
            natural_variation = base_question.replace("headquartered", "located")
        else:
            natural_variation = base_question.replace("Where is", "What is the address of")
    
    elif category == "Mutual Status":
        if "mutual or one-way" in base_question.lower():
            natural_variation = base_question.replace("mutual or one-way", "bidirectional or unidirectional")
        elif "bidirectional" in base_question.lower():
            natural_variation = base_question.replace("bidirectional or unidirectional", "mutual or one-way")
        else:
            natural_variation = base_question.replace("Is the", "Does the").replace("mutual or one-way", "apply to both parties")
    
    # Fallback for natural variation
    if not natural_variation:
        if "What is" in base_question:
            natural_variation = base_question.replace("What is", "What's")
        elif "NDA" in base_question:
            natural_variation = base_question.replace("NDA", "agreement")
        else:
            natural_variation = base_question.replace("?", "?").replace("the ", "this ")
    
    variations.append({
        "question": natural_variation,
        "confidence": 0.8,  # High confidence for natural rephrasing
        "has_misspelling": False,
        "variation_type": "natural"
    })
    
    # Variation 2: Misspelling (lower confidence)
    misspelled_variation = introduce_misspellings(base_question, severity="medium")
    variations.append({
        "question": misspelled_variation,
        "confidence": 0.6,  # Lower confidence for misspellings
        "has_misspelling": True,
        "variation_type": "misspelling"
    })
    
    return variations


def get_natural_company_name_variations(full_company_name: str) -> List[str]:
    """Get natural variations of company name that users would actually say
    
    Examples:
        "KGS Fire & Security B.V. Sept. 2028" -> ["KGS Fire", "KGS Fire & Security"]
        "Vallen Distribution, Inc. July 2028" -> ["Vallen", "Vallen Distribution"]
        "Fanuc America Corporation June 2028" -> ["Fanuc", "Fanuc America"]
    """
    # Remove date suffixes and common patterns
    name = full_company_name
    
    # Remove date patterns (e.g., "Sept. 2028", "July 2028", "June 2028")
    import re
    name = re.sub(r'\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+\d{4}', '', name)  # Remove any remaining year
    
    # Remove common suffixes
    name = re.sub(r'\s+(Inc\.?|LLC|Corp\.?|Corporation|Ltd\.?|B\.V\.?|SDN BHD|Co\.?|Company)\s*$', '', name, flags=re.IGNORECASE)
    
    # Clean up trailing commas and punctuation
    name = name.rstrip(',. ')
    
    # Get natural variations - prioritize 2-word names (most natural)
    variations = []
    words = name.split()
    
    # First two words (most natural - e.g., "KGS Fire", "Vallen Distribution", "Fanuc America")
    if len(words) >= 2:
        two_words = ' '.join(words[:2])
        variations.append(two_words)
    
    # First word only (if it's a full word, not just initials)
    first_word = words[0] if words else name
    # Only use single word if it's at least 4 chars (like "Vallen", "Boston") 
    # or if it's a known full word (not just initials like "KGS")
    if first_word and (len(first_word) >= 4 or (len(first_word) >= 3 and not first_word.isupper())):
        if two_words not in variations or first_word.lower() != two_words.split()[0].lower():
            variations.append(first_word)
    
    # Full name without suffixes (if reasonable length and different)
    clean_full = name.strip()
    if clean_full and clean_full not in variations and len(clean_full.split()) <= 4:
        variations.append(clean_full)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for v in variations:
        if v.lower() not in seen:
            seen.add(v.lower())
            unique_variations.append(v)
    
    # Always return at least the first two words (most natural)
    if not unique_variations and len(words) >= 2:
        unique_variations.append(' '.join(words[:2]))
    elif not unique_variations:
        unique_variations.append(words[0] if words else name)
    
    return unique_variations[:3]  # Return up to 3 variations, first is most natural


def generate_questions_for_document(doc_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate document-specific questions for a single document"""
    questions = []
    company_name = doc_info['company_name']
    
    # Get natural company name variations (what users would actually say)
    name_variations = get_natural_company_name_variations(company_name)
    
    # 1. Governing law questions (company-specific)
    if doc_info.get('governing_law'):
        state = doc_info['governing_law'].split()[-1] if doc_info['governing_law'] else None
        if state:
            # Base question - use shortest natural name
            base_question = f"What is the governing state of {name_variations[0]}?"
            base_q_dict = {
                "question": base_question,
                "expected_contains": [state],
                "min_confidence": 0.8,
                "description": f"Governing law for {company_name}",
                "document_id": doc_info['doc_id'],
                "category": "Governing Law"
            }
            questions.append(base_q_dict)
            
            # Generate 2 variations
            variations = generate_question_variations(base_question, "Governing Law", doc_info)
            for var_data in variations:
                questions.append({
                    "question": var_data["question"],
                    "expected_contains": [state],
                    "min_confidence": var_data["confidence"],
                    "description": f"Governing law for {company_name} ({var_data['variation_type']})",
                    "document_id": doc_info['doc_id'],
                    "category": "Governing Law",
                    "is_variation": True,
                    "base_question": base_question,
                    "has_misspelling": var_data["has_misspelling"],
                    "variation_type": var_data["variation_type"]
                })
    
    # 2. Effective date questions (company-specific)
    if doc_info.get('effective_date'):
        # Use natural phrasing - users might say "the [Company] NDA" or just "[Company]"
        base_question = f"When did the {name_variations[0]} NDA become effective?"
        base_q_dict = {
            "question": base_question,
            "expected_contains": [doc_info['effective_date'][:7]],  # Year-month
            "min_confidence": 0.8,
            "description": f"Effective date for {company_name}",
            "document_id": doc_info['doc_id'],
            "category": "Effective Date"
        }
        questions.append(base_q_dict)
        
        # Generate 2 variations
        variations = generate_question_variations(base_question, "Effective Date", doc_info)
        for var_data in variations:
            questions.append({
                "question": var_data["question"],
                "expected_contains": [doc_info['effective_date'][:7]],
                "min_confidence": var_data["confidence"],
                "description": f"Effective date for {company_name} ({var_data['variation_type']})",
                "document_id": doc_info['doc_id'],
                "category": "Effective Date",
                "is_variation": True,
                "base_question": base_question,
                "has_misspelling": var_data["has_misspelling"],
                "variation_type": var_data["variation_type"]
            })
    
    # 3. Expiration date questions (company-specific)
    if doc_info.get('expiration_date'):
        base_question = f"What date does the {name_variations[0]} NDA expire?"
        base_q_dict = {
            "question": base_question,
            "expected_contains": [doc_info['expiration_date'][:7]],  # Year-month
            "min_confidence": 0.8,
            "description": f"Expiration date for {company_name}",
            "document_id": doc_info['doc_id'],
            "category": "Expiration Date"
        }
        questions.append(base_q_dict)
        
        # Generate 2 variations
        variations = generate_question_variations(base_question, "Expiration Date", doc_info)
        for var_data in variations:
            questions.append({
                "question": var_data["question"],
                "expected_contains": [doc_info['expiration_date'][:7]],
                "min_confidence": var_data["confidence"],
                "description": f"Expiration date for {company_name} ({var_data['variation_type']})",
                "document_id": doc_info['doc_id'],
                "category": "Expiration Date",
                "is_variation": True,
                "base_question": base_question,
                "has_misspelling": var_data["has_misspelling"],
                "variation_type": var_data["variation_type"]
            })
    
    # 4. Term questions (company-specific)
    if doc_info.get('term_months'):
        base_question = f"What is the term of the {name_variations[0]} NDA?"
        base_q_dict = {
            "question": base_question,
            "expected_contains": [str(doc_info['term_months'])],
            "min_confidence": 0.8,
            "description": f"Term for {company_name}",
            "document_id": doc_info['doc_id'],
            "category": "Term"
        }
        questions.append(base_q_dict)
        
        # Generate 2 variations
        variations = generate_question_variations(base_question, "Term", doc_info)
        for var_data in variations:
            questions.append({
                "question": var_data["question"],
                "expected_contains": [str(doc_info['term_months'])],
                "min_confidence": var_data["confidence"],
                "description": f"Term for {company_name} ({var_data['variation_type']})",
                "document_id": doc_info['doc_id'],
                "category": "Term",
                "is_variation": True,
                "base_question": base_question,
                "has_misspelling": var_data["has_misspelling"],
                "variation_type": var_data["variation_type"]
            })
    
    # 5. Location/Address questions (company-specific)
    if doc_info.get('parties'):
        for party in doc_info['parties']:
            if party.get('address'):
                # Extract city/state from address
                address_parts = party['address'].split(',')
                if len(address_parts) >= 2:
                    city = address_parts[-2].strip() if len(address_parts) >= 2 else None
                    state = address_parts[-1].strip().split()[0] if address_parts else None
                    
                    if city:
                        # Users would say "Where is [Company]?" not the full name
                        base_question = f"Where is {name_variations[0]} located?"
                        base_q_dict = {
                            "question": base_question,
                            "expected_contains": [city, state] if state else [city],
                            "min_confidence": 0.7,
                            "description": f"Location for {company_name}",
                            "document_id": doc_info['doc_id'],
                            "category": "Location"
                        }
                        questions.append(base_q_dict)
                        
                        # Generate 2 variations
                        variations = generate_question_variations(base_question, "Location", doc_info)
                        for var_data in variations:
                            questions.append({
                                "question": var_data["question"],
                                "expected_contains": [city, state] if state else [city],
                                "min_confidence": var_data["confidence"],
                                "description": f"Location for {company_name} ({var_data['variation_type']})",
                                "document_id": doc_info['doc_id'],
                                "category": "Location",
                                "is_variation": True,
                                "base_question": base_question,
                                "has_misspelling": var_data["has_misspelling"],
                                "variation_type": var_data["variation_type"]
                            })
                    break  # Only one location question per company
    
    # 6. Parties questions (company-specific)
    if doc_info.get('parties') and len(doc_info['parties']) >= 2:
        party_names = [p['name'] for p in doc_info['parties']]
        base_question = f"Who are the parties to the {name_variations[0]} NDA?"
        base_q_dict = {
            "question": base_question,
            "expected_contains": party_names[:2],  # First 2 parties
            "min_confidence": 0.8,
            "description": f"Parties for {company_name}",
            "document_id": doc_info['doc_id'],
            "category": "Parties"
        }
        questions.append(base_q_dict)
        
        # Generate 2 variations
        variations = generate_question_variations(base_question, "Parties", doc_info)
        for var_data in variations:
            questions.append({
                "question": var_data["question"],
                "expected_contains": party_names[:2],
                "min_confidence": var_data["confidence"],
                "description": f"Parties for {company_name} ({var_data['variation_type']})",
                "document_id": doc_info['doc_id'],
                "category": "Parties",
                "is_variation": True,
                "base_question": base_question,
                "has_misspelling": var_data["has_misspelling"],
                "variation_type": var_data["variation_type"]
            })
    
    # 7. Mutual status questions (company-specific)
    if doc_info.get('is_mutual') is not None:
        mutual_text = "mutual" if doc_info['is_mutual'] else "one-way"
        base_question = f"Is the {name_variations[0]} NDA mutual or one-way?"
        base_q_dict = {
            "question": base_question,
            "expected_contains": [mutual_text],
            "min_confidence": 0.8,
            "description": f"Mutual status for {company_name}",
            "document_id": doc_info['doc_id'],
            "category": "Mutual Status"
        }
        questions.append(base_q_dict)
        
        # Generate 2 variations
        variations = generate_question_variations(base_question, "Mutual Status", doc_info)
        for var_data in variations:
            questions.append({
                "question": var_data["question"],
                "expected_contains": [mutual_text],
                "min_confidence": var_data["confidence"],
                "description": f"Mutual status for {company_name} ({var_data['variation_type']})",
                "document_id": doc_info['doc_id'],
                "category": "Mutual Status",
                "is_variation": True,
                "base_question": base_question,
                "has_misspelling": var_data["has_misspelling"],
                "variation_type": var_data["variation_type"]
            })
    
    return questions


def main():
    """Generate document-specific questions for all documents"""
    print("Generating document-specific questions...")
    print("=" * 80)
    
    # Get all document info
    doc_info_list = get_document_specific_info()
    
    print(f"\nFound {len(doc_info_list)} documents")
    
    # Generate questions for each document
    all_questions = []
    for doc_info in doc_info_list:
        questions = generate_questions_for_document(doc_info)
        all_questions.extend(questions)
        print(f"\n{doc_info['company_name']}: {len(questions)} questions")
    
    print(f"\n\nTotal questions generated: {len(all_questions)}")
    
    # Count base questions vs variations
    base_questions = [q for q in all_questions if not q.get('is_variation', False)]
    variations = [q for q in all_questions if q.get('is_variation', False)]
    natural_vars = [q for q in variations if not q.get('has_misspelling', False)]
    misspelled_vars = [q for q in variations if q.get('has_misspelling', False)]
    
    print(f"  Base questions: {len(base_questions)}")
    print(f"  Variations: {len(variations)}")
    print(f"    - Natural rephrasing: {len(natural_vars)}")
    print(f"    - With misspellings: {len(misspelled_vars)}")
    
    # Group by category
    by_category = {}
    for q in all_questions:
        cat = q.get('category', 'Other')
        if cat not in by_category:
            by_category[cat] = {'base': 0, 'natural': 0, 'misspelled': 0}
        if q.get('is_variation', False):
            if q.get('has_misspelling', False):
                by_category[cat]['misspelled'] += 1
            else:
                by_category[cat]['natural'] += 1
        else:
            by_category[cat]['base'] += 1
    
    print("\nQuestions by category:")
    for cat in sorted(by_category.keys()):
        stats = by_category[cat]
        total = stats['base'] + stats['natural'] + stats['misspelled']
        print(f"  {cat}: {total} total ({stats['base']} base + {stats['natural']} natural + {stats['misspelled']} misspelled)")
    
    # Confidence level distribution
    confidence_levels = {}
    for q in all_questions:
        conf = q.get('min_confidence', 0.7)
        conf_key = f"{conf:.1f}"
        confidence_levels[conf_key] = confidence_levels.get(conf_key, 0) + 1
    
    print("\nConfidence level distribution:")
    for conf_level in sorted(confidence_levels.keys(), reverse=True):
        print(f"  {conf_level}: {confidence_levels[conf_level]} questions")
    
    # Save to JSON
    output_file = Path(__file__).parent.parent / 'document_specific_questions.json'
    with open(output_file, 'w') as f:
        json.dump(all_questions, f, indent=2)
    
    print(f"\n✅ Saved questions to {output_file}")
    
    # Also save a human-readable review file
    review_file = Path(__file__).parent.parent / 'document_specific_questions_REVIEW.md'
    with open(review_file, 'w') as f:
        f.write("# Document-Specific Questions for Review\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total Questions: {len(all_questions)} ({len(base_questions)} base + {len(natural_vars)} natural + {len(misspelled_vars)} misspelled)\n\n")
        
        # Group by document
        by_document = {}
        for q in all_questions:
            doc_id = q.get('document_id', 'unknown')
            if doc_id not in by_document:
                by_document[doc_id] = []
            by_document[doc_id].append(q)
        
        for doc_id, doc_questions in by_document.items():
            # Get document name from first question
            doc_name = doc_questions[0].get('description', '').split(' for ')[-1] if ' for ' in doc_questions[0].get('description', '') else doc_id
            f.write(f"## {doc_name}\n\n")
            
            # Group by category
            by_cat = {}
            for q in doc_questions:
                cat = q.get('category', 'Other')
                if cat not in by_cat:
                    by_cat[cat] = []
                by_cat[cat].append(q)
            
            for cat in sorted(by_cat.keys()):
                f.write(f"### {cat}\n\n")
                for q in by_cat[cat]:
                    is_var = q.get('is_variation', False)
                    has_misspelling = q.get('has_misspelling', False)
                    var_type = q.get('variation_type', '')
                    conf = q.get('min_confidence', 0.7)
                    
                    if has_misspelling:
                        marker = "❌"
                    elif is_var:
                        marker = "🔄"
                    else:
                        marker = "📌"
                    
                    f.write(f"{marker} **Q:** {q['question']}\n")
                    f.write(f"   - Expected: {', '.join(q.get('expected_contains', []))}\n")
                    f.write(f"   - Min Confidence: {conf:.2f}\n")
                    if is_var:
                        f.write(f"   - Base: {q.get('base_question', 'N/A')}\n")
                        f.write(f"   - Type: {var_type}\n")
                    f.write("\n")
                f.write("\n")
    
    print(f"✅ Saved review file to {review_file}")
    
    return all_questions


if __name__ == '__main__':
    main()

