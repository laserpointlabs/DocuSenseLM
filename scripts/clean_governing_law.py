#!/usr/bin/env python3
"""
Script to clean governing law values in the database by removing trailing clauses
"""
import os
import sys
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import Document, DocumentMetadata, DocumentStatus

def clean_governing_law(law: str) -> str:
    """Clean governing law by removing trailing clauses"""
    if not law:
        return None

    # Clean up common suffixes and trailing clauses
    law = re.sub(r'\s+excluding.*$', '', law, flags=re.IGNORECASE)
    law = re.sub(r'\s+without.*$', '', law, flags=re.IGNORECASE)
    law = re.sub(r'\s+conflicts?\s+of\s+law.*$', '', law, flags=re.IGNORECASE)
    law = re.sub(r'\s+principles.*$', '', law, flags=re.IGNORECASE)
    law = re.sub(r'\s+thereof.*$', '', law, flags=re.IGNORECASE)
    # Remove trailing punctuation
    law = law.rstrip('.,;')
    # Normalize whitespace (multiple spaces to single space)
    law = re.sub(r'\s+', ' ', law)
    law = law.strip()

    # Format as "State of X" if needed
    if law and len(law) > 3:
        # Remove "the" prefix if present (case-insensitive)
        law_lower = law.lower()
        if law_lower.startswith('the state of '):
            # "the State of Delaware" -> "State of Delaware"
            law = law[len('the '):]  # Remove "the " prefix
        elif law_lower.startswith('the ') and 'state' not in law_lower:
            # Just "the Delaware" -> "State of Delaware"
            law = law[len('the '):]  # Remove "the " prefix

        # Normalize "State of" format
        law_lower = law.lower()
        if law_lower.startswith('state of '):
            # Extract state name (remove "state of " prefix)
            state_name = law[len('State of '):].strip()
            # Handle edge cases like "State of the  Delaware" -> "State of Delaware"
            state_name = re.sub(r'^\s*the\s+', '', state_name, flags=re.IGNORECASE)
            state_name = re.sub(r'\s+', ' ', state_name).strip()
            if state_name:
                return f"State of {state_name}"
        else:
            # If it's just a state name, add "State of" prefix
            if not any(word in law.lower() for word in ['state', 'province', 'country']):
                return f"State of {law}"

        return law

    return None


def update_governing_laws():
    """Update governing law values in the database"""
    db = get_db_session()
    try:
        documents = db.query(Document).filter(
            Document.status == DocumentStatus.PROCESSED
        ).all()

        print(f"📋 Processing {len(documents)} documents...")
        print()

        updated_count = 0

        for doc in documents:
            metadata = db.query(DocumentMetadata).filter(
                DocumentMetadata.document_id == doc.id
            ).first()

            if not metadata or not metadata.governing_law:
                continue

            original = metadata.governing_law
            cleaned = clean_governing_law(original)

            if cleaned and cleaned != original:
                metadata.governing_law = cleaned
                updated_count += 1
                print(f"✅ Updated {doc.filename[:50]:50}")
                print(f"   From: {original}")
                print(f"   To:   {cleaned}")
                print()

        db.commit()
        print(f"✅ Updated {updated_count} documents with cleaned governing law")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 70)
    print("Clean Governing Law Values")
    print("=" * 70)
    print()

    update_governing_laws()

    print()
    print("=" * 70)
    print("Done!")
    print("=" * 70)
