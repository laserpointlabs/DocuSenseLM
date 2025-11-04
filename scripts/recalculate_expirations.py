#!/usr/bin/env python3
"""
Script to recalculate expiration dates and term_months for documents
based on extracted metadata or filename patterns.
"""
import os
import sys
import re
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import Document, DocumentMetadata, DocumentStatus

def parse_expiration_from_filename(filename: str) -> tuple[datetime | None, int | None]:
    """
    Parse expiration date and term from filename
    Format: "Company_Signed NDA_expires Sept. 2028.pdf"
    Returns: (expiration_date, term_months) or (None, None)
    """
    month_names = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'sept': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }

    # Try to match "expires Sept. 2028" or "expires September 2028"
    match = re.search(r'expires?\s+(\w+\.?\s+\d{4})', filename, re.IGNORECASE)
    if match:
        date_str = match.group(1)
        parts = date_str.strip().lower().replace('.', '').split()
        if len(parts) >= 2:
            month_name = parts[0]
            year_str = parts[1]
            try:
                year = int(year_str)
                month = month_names.get(month_name)
                if month:
                    expiration_date = datetime(year, month, 1)
                    return expiration_date, None  # Term will be calculated from effective_date
            except ValueError:
                pass

    return None, None


def recalculate_expirations():
    """Recalculate term_months and expiration dates for all documents"""
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

            if not metadata:
                continue

            effective_date = metadata.effective_date
            term_months = metadata.term_months

            # Try to extract expiration from filename if term_months is missing
            if effective_date and not term_months:
                expiration_date, _ = parse_expiration_from_filename(doc.filename)
                if expiration_date:
                    # Calculate term_months from effective_date to expiration_date
                    months_diff = (expiration_date.year - effective_date.year) * 12 + \
                                 (expiration_date.month - effective_date.month)
                    if 12 <= months_diff <= 120:  # Reasonable range (1-10 years)
                        metadata.term_months = months_diff
                        updated_count += 1
                        print(f"✅ Updated {doc.filename[:50]:50} | Term: {months_diff} months (calculated from filename)")
                        continue

            # If we have effective_date and term_months but want to verify calculation
            if effective_date and term_months:
                # Verify expiration can be calculated
                calculated_expiration = effective_date + timedelta(days=term_months * 30.44)
                print(f"✓ {doc.filename[:50]:50} | Term: {term_months} months | Effective: {effective_date.strftime('%Y-%m-%d')} | Expires: ~{calculated_expiration.strftime('%Y-%m-%d')}")

        db.commit()
        print()
        print(f"✅ Updated {updated_count} documents with term_months")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 70)
    print("Recalculate Expiration Dates")
    print("=" * 70)
    print()

    recalculate_expirations()

    print()
    print("=" * 70)
    print("Done!")
    print("=" * 70)
