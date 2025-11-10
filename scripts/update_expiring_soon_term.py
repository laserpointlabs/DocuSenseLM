#!/usr/bin/env python3
"""
Update term_months for the expiring soon PDF based on filename expiration date.
"""
import sys
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import get_db_session
from api.db.schema import Document, DocumentMetadata

def update_expiring_soon_term():
    """Update term_months for expiring soon PDF"""
    db = get_db_session()
    try:
        # Find the expiring soon document
        doc = db.query(Document).filter(Document.filename.like('%Jan. 2026%')).first()
        if not doc:
            print("❌ Document with 'Jan. 2026' not found")
            return
        
        meta = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == doc.id).first()
        if not meta:
            print("❌ No metadata found for document")
            return
        
        if not meta.effective_date:
            print("❌ No effective_date found")
            return
        
        # Parse expiration from filename: "Expires Jan. 2026"
        expiration_date = datetime(2026, 1, 9)  # January 9, 2026 (60 days from now)
        
        # Calculate term_months from effective_date to expiration_date
        effective = meta.effective_date
        if effective.tzinfo:
            effective = effective.replace(tzinfo=None)
        
        # Calculate months difference
        months_diff = (expiration_date.year - effective.year) * 12 + (expiration_date.month - effective.month)
        
        print(f'Document: {doc.filename}')
        print(f'Effective date: {effective}')
        print(f'Expiration date (from filename): {expiration_date}')
        print(f'Calculated term_months: {months_diff}')
        
        # Update term_months
        meta.term_months = months_diff
        db.commit()
        print(f'✅ Updated term_months to {months_diff}')
        
        # Verify calculation
        expiration_calc = effective + relativedelta(months=months_diff)
        today = datetime.now().date()
        days_diff = (expiration_calc.date() - today).days
        print(f'Calculated expiration: {expiration_calc.date()}')
        print(f'Days until expiration: {days_diff}')
        print(f'Status: {"EXPIRING SOON" if 0 < days_diff <= 90 else "EXPIRED" if days_diff < 0 else "ACTIVE"}')
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    update_expiring_soon_term()

