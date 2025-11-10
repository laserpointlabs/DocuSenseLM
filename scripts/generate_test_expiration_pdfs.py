#!/usr/bin/env python3
"""
Generate test PDFs with near-expiration and expired dates for testing expiration detection.

This script copies existing NDA PDFs and creates versions with:
- Near expiration dates (30, 60, 90 days from now)
- Expired dates (30, 60 days ago)
"""
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

def get_month_name(month_num):
    """Get month name abbreviation"""
    months = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sept', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    }
    return months.get(month_num, 'Jan')

def generate_test_pdfs():
    """Generate test PDFs with various expiration dates"""
    data_dir = Path('data')
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return
    
    # Find existing PDFs
    existing_pdfs = list(data_dir.glob('*.pdf'))
    if not existing_pdfs:
        print(f"❌ No PDFs found in {data_dir}")
        return
    
    print(f"Found {len(existing_pdfs)} existing PDFs")
    
    # Calculate dates
    today = datetime.now()
    
    # Near expiration dates
    near_expiry_dates = [
        (today + timedelta(days=30), "30 days"),
        (today + timedelta(days=60), "60 days"),
        (today + timedelta(days=90), "90 days"),
    ]
    
    # Expired dates
    expired_dates = [
        (today - timedelta(days=30), "30 days ago"),
        (today - timedelta(days=60), "60 days ago"),
    ]
    
    # Use first 2 PDFs as templates
    templates = existing_pdfs[:2]
    
    created_files = []
    
    # Generate near-expiration PDFs
    print("\n📅 Creating near-expiration PDFs...")
    for i, template in enumerate(templates):
        for expiry_date, label in near_expiry_dates:
            # Extract company name from original filename
            original_name = template.stem
            # Remove existing expiration info if present
            company_name = original_name.split('_Signed NDA')[0].split('_SIGNED NDA')[0]
            
            month_name = get_month_name(expiry_date.month)
            year = expiry_date.year
            
            # Create new filename
            new_filename = f"{company_name}_Signed NDA_Expires {month_name}. {year}.pdf"
            new_path = data_dir / new_filename
            
            # Copy the PDF
            shutil.copy2(template, new_path)
            created_files.append((new_path, expiry_date, "near_expiration"))
            print(f"  ✓ Created: {new_filename} (expires in {label})")
    
    # Generate expired PDFs
    print("\n⏰ Creating expired PDFs...")
    for i, template in enumerate(templates):
        for expiry_date, label in expired_dates:
            # Extract company name from original filename
            original_name = template.stem
            company_name = original_name.split('_Signed NDA')[0].split('_SIGNED NDA')[0]
            
            month_name = get_month_name(expiry_date.month)
            year = expiry_date.year
            
            # Create new filename
            new_filename = f"{company_name}_Signed NDA_Expires {month_name}. {year}.pdf"
            new_path = data_dir / new_filename
            
            # Copy the PDF
            shutil.copy2(template, new_path)
            created_files.append((new_path, expiry_date, "expired"))
            print(f"  ✓ Created: {new_filename} (expired {label})")
    
    print(f"\n✅ Created {len(created_files)} test PDFs")
    print("\n📊 Summary:")
    print(f"  Near expiration (30-90 days): {len([f for f in created_files if f[2] == 'near_expiration'])}")
    print(f"  Expired (30-60 days ago): {len([f for f in created_files if f[2] == 'expired'])}")
    print("\n💡 Next steps:")
    print("  1. Upload these PDFs via the Admin page")
    print("  2. Check the Dashboard to see if they're detected as expiring soon or expired")
    print("  3. Test filtering by expiration status")

if __name__ == "__main__":
    generate_test_pdfs()

