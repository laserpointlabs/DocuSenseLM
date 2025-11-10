#!/usr/bin/env python3
"""
Modify a PDF's expiration date by extracting text, modifying expiration references,
and creating a new PDF with the updated content.
"""
import sys
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ingest.parser import DocumentParser
    import PyPDF2
except ImportError:
    print("❌ Required libraries not found. Run this script in the Docker container:")
    print("   docker compose exec -T api python scripts/modify_pdf_expiration.py")
    sys.exit(1)

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    print("❌ reportlab not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont


def get_month_name(month_num):
    """Get full month name"""
    months = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
        7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }
    return months.get(month_num, 'January')


def get_month_abbrev(month_num):
    """Get month abbreviation"""
    months = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Aug', 9: 'Sept', 10: 'Oct', 11: 'Nov', 12: 'Dec'
    }
    return months.get(month_num, 'Jan')


def modify_expiration_dates(text, new_expiration_date, effective_date=None):
    """Modify expiration date references in text and add term duration"""
    modified_text = text
    
    # Calculate term in months from effective_date to expiration_date
    # If effective_date not provided, try to extract it from text
    if effective_date is None:
        # Try to find effective date in text - handle "202 5" format
        date_patterns = [
            r'entered\s+into\s+as\s+of\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})\s*(\d{0,4})',  # Handle "202 5"
            r'entered\s+into\s+as\s+of\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})',
            r'effective\s+date[:\s]+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                month_name = match.group(1)
                day = int(match.group(2))
                year_str = match.group(3) + (match.group(4) if len(match.groups()) > 3 and match.group(4) else '')
                year = int(year_str.replace(' ', ''))
                month_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month = month_map.get(month_name.lower(), None)
                if month:
                    effective_date = datetime(year, month, day)
                    break
    
    # Calculate term_months if we have effective_date
    # IMPORTANT: Extractor only accepts 12-120 months (1-10 years)
    # So we need to adjust effective_date to make term at least 12 months
    term_months = None
    adjusted_effective_date = effective_date
    
    if effective_date:
        months_diff = (new_expiration_date.year - effective_date.year) * 12 + \
                     (new_expiration_date.month - effective_date.month)
        
        # If term is less than 12 months, adjust effective_date backwards to make it 12 months
        if months_diff < 12:
            # Set effective_date to be exactly 12 months before expiration
            from dateutil.relativedelta import relativedelta
            adjusted_effective_date = new_expiration_date - relativedelta(months=12)
            term_months = 12
            print(f"⚠️  Term would be {months_diff} months - adjusting effective date to {adjusted_effective_date.strftime('%B %d, %Y')} to make it 12 months")
        elif months_diff <= 120:
            term_months = months_diff
        else:
            print(f"⚠️  Term {months_diff} months is too long (max 120)")
            return modified_text
    
    if not term_months:
        print("⚠️  Cannot calculate term_months - effective_date not found or invalid")
        return modified_text
    
    # Update effective_date in text to match adjusted date
    if adjusted_effective_date != effective_date:
        # Replace effective date in text
        date_pattern = re.compile(
            r'entered\s+into\s+as\s+of\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{3})\s+(\d)',
            re.IGNORECASE
        )
        new_date_str = adjusted_effective_date.strftime("%B %d, %Y")
        def replace_date(match):
            return f"entered into as of {new_date_str}"
        modified_text = date_pattern.sub(replace_date, modified_text)
    
    # Format term text that extractor will recognize
    # The extractor looks for patterns like "term of 5 months" or "5 (5) months"
    if term_months >= 12:
        years = term_months // 12
        months_remainder = term_months % 12
        if months_remainder == 0:
            # Use format extractor recognizes: "term of three (3) years"
            year_words = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
            if years <= 10:
                term_text = f"{year_words[years]} ({years}) year{'s' if years > 1 else ''}"
            else:
                term_text = f"{years} ({years}) years"
        else:
            term_text = f"{years} ({years}) year{'s' if years > 1 else ''} and {months_remainder} ({months_remainder}) month{'s' if months_remainder > 1 else ''}"
    else:
        # For months < 12, use format: "5 (5) months"
        term_text = f"{term_months} ({term_months}) month{'s' if term_months > 1 else ''}"
    
    # Replace the term clause - find "the date which is three (3) year s after"
    # Handle variable whitespace - match the exact format in the PDF
    pattern_term = re.compile(
        r'the\s+date\s+which\s+is\s+three\s*\(\s*3\s*\)\s*year\s*s?\s+after\s+the\s+date',
        re.IGNORECASE
    )
    # Use format extractor recognizes: "X (X) months after the date hereof" 
    # But extractor also looks for "after the date" patterns
    modified_text = pattern_term.sub(f"the date which is {term_text} after the date hereof", modified_text)
    
    # Also replace standalone "three (3) years" patterns  
    pattern_standalone = re.compile(
        r'three\s*\(\s*3\s*\)\s*year\s*s?\s+after',
        re.IGNORECASE
    )
    modified_text = pattern_standalone.sub(f"{term_text} after the date hereof", modified_text)
    
    # Replace the entire term clause with a clean version the extractor will recognize
    # Pattern: "8. Term . This Agreement shall automatically terminate on the date which is..."
    term_clause_full_pattern = re.compile(
        r'(8\.\s*Term\s*\.?\s*This\s+Agreement\s+shall\s+automatically\s+terminate\s+on\s+the\s+date\s+which\s+is\s+).*?(?=\d+\.\s+|$)',
        re.IGNORECASE | re.DOTALL
    )
    # Use format extractor recognizes: "term of 5 months" (simple number, not "5 (5)")
    if term_months >= 12:
        years = term_months // 12
        term_simple = f"{years} year{'s' if years > 1 else ''}"
    else:
        term_simple = f"{term_months} month{'s' if term_months > 1 else ''}"
    
    def replace_term_clause(match):
        return f"{match.group(1)}{term_simple} after the date hereof, provided, however, that any obligation of confidentiality with respect to any information that qualifies as a trade secret under the requirements of any applicable law will survive as long as that information is classified as such."
    
    modified_text = term_clause_full_pattern.sub(replace_term_clause, modified_text, count=1)
    
    # Also ensure "term of X months" appears somewhere for the extractor
    if f"term of {term_months}" not in modified_text.lower():
        # Add it right after "8. Term"
        term_header_pattern = re.compile(
            r'(8\.\s*Term\s*\.?\s*)',
            re.IGNORECASE
        )
        def add_term(match):
            return f"{match.group(1)}This Agreement shall continue for a term of {term_simple}. "
        modified_text = term_header_pattern.sub(add_term, modified_text, count=1)
    
    # Replace "expires [Month] [Year]" patterns in filename context
    month_names = r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?'
    year_pattern = r'\d{4}'
    new_month = get_month_name(new_expiration_date.month)
    new_year = str(new_expiration_date.year)
    
    pattern_expires = re.compile(
        r'expires?\s+' + month_names + r'\.?\s+' + year_pattern,
        re.IGNORECASE
    )
    modified_text = pattern_expires.sub(f"expires {new_month} {new_year}", modified_text)
    
    return modified_text


def create_modified_pdf(source_pdf_path, output_pdf_path, expiration_date):
    """Create a new PDF with modified expiration date"""
    print(f"📄 Extracting text from: {source_pdf_path}")
    
    # Parse the original PDF
    parser = DocumentParser()
    parsed = parser.parse(str(source_pdf_path))
    
    full_text = parsed['text']
    pages = parsed['pages']
    
    print(f"✓ Extracted {len(pages)} pages")
    
    # Try to extract effective date from text - handle "202 5" format with spaces
    effective_date = None
    # Match "August  11, 202 5" - handle spaces in year
    match = re.search(r'entered\s+into\s+as\s+of\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{3})\s+(\d)', full_text, re.IGNORECASE)
    if match:
        month_name = match.group(1)
        day = int(match.group(2))
        year = int(match.group(3) + match.group(4))  # Combine "202" + "5" = 2025
        month_map = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        month = month_map.get(month_name.lower(), None)
        if month:
            effective_date = datetime(year, month, day)
            print(f"✓ Found effective date: {effective_date.strftime('%B %d, %Y')}")
    
    # Fallback to normal format if first pattern didn't match
    if not effective_date:
        date_patterns = [
            r'entered\s+into\s+as\s+of\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})',
            r'as\s+of\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                month_name = match.group(1)
                day = int(match.group(2))
                year = int(match.group(3))
                month_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month = month_map.get(month_name.lower(), None)
                if month:
                    effective_date = datetime(year, month, day)
                    print(f"✓ Found effective date: {effective_date.strftime('%B %d, %Y')}")
                    break
    
    if not effective_date:
        print("❌ Could not find effective date in PDF - cannot calculate term")
        return
    
    # Modify expiration dates in text and add term duration
    print(f"✏️  Modifying expiration dates to: {expiration_date.strftime('%B %d, %Y')}")
    modified_text = modify_expiration_dates(full_text, expiration_date, effective_date)
    
    # Create new PDF with modified text
    print(f"📝 Creating new PDF: {output_pdf_path}")
    
    doc = SimpleDocTemplate(
        str(output_pdf_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Build PDF content
    story = []
    styles = getSampleStyleSheet()
    
    # Use a normal style for body text
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        spaceAfter=12,
    )
    
    # Split text into paragraphs and add to PDF
    paragraphs = modified_text.split('\n\n')
    
    for i, para in enumerate(paragraphs):
        if para.strip():
            # Clean up the paragraph text
            para_clean = para.strip().replace('\n', ' ')
            # Escape special characters for ReportLab
            para_clean = para_clean.replace('&', '&amp;')
            para_clean = para_clean.replace('<', '&lt;')
            para_clean = para_clean.replace('>', '&gt;')
            
            story.append(Paragraph(para_clean, normal_style))
            story.append(Spacer(1, 6))
        
        # Add page break every ~40 paragraphs (approximate page)
        if i > 0 and i % 40 == 0:
            story.append(PageBreak())
    
    # Build PDF
    doc.build(story)
    
    print(f"✅ Created modified PDF: {output_pdf_path}")


def main():
    """Main function"""
    data_dir = Path('data')
    
    # Find a source PDF
    source_pdfs = list(data_dir.glob('*.pdf'))
    if not source_pdfs:
        print(f"❌ No PDFs found in {data_dir}")
        return
    
    # Use a different PDF as source (not the expired one)
    source_pdf = None
    for pdf in source_pdfs:
        if 'Sept. 2025' not in pdf.name:  # Skip the expired one we already created
            source_pdf = pdf
            break
    if not source_pdf:
        source_pdf = source_pdfs[0]  # Fallback to first PDF
    
    print(f"📋 Using source PDF: {source_pdf.name}")
    
    # Calculate expiring soon date (60 days from now - within 90 day window)
    # For extractor to work, we need term >= 12 months, so effective_date will be adjusted
    expiring_date = datetime.now() + timedelta(days=60)
    
    # Also create expired PDF (60 days ago)
    expired_date = datetime.now() - timedelta(days=60)
    
    # Create expiring soon PDF
    company_name = source_pdf.stem.split('_Signed NDA')[0].split('_SIGNED NDA')[0]
    month_abbrev = get_month_abbrev(expiring_date.month)
    output_filename_expiring = f"{company_name}_Signed NDA_Expires {month_abbrev}. {expiring_date.year}.pdf"
    output_path_expiring = Path('/tmp') / output_filename_expiring
    print(f"\n📄 Creating EXPIRING SOON PDF:")
    create_modified_pdf(source_pdf, output_path_expiring, expiring_date)
    
    # Create expired PDF
    month_abbrev_expired = get_month_abbrev(expired_date.month)
    output_filename_expired = f"{company_name}_Signed NDA_Expires {month_abbrev_expired}. {expired_date.year}.pdf"
    output_path_expired = Path('/tmp') / output_filename_expired
    print(f"\n📄 Creating EXPIRED PDF:")
    create_modified_pdf(source_pdf, output_path_expired, expired_date)
    
    # Copy both to host
    output_path = output_path_expiring  # For compatibility with rest of script
    output_filename = output_filename_expiring
    
    # Copy to host data directory using docker cp
    final_output_path = data_dir / output_filename
    import subprocess
    try:
        # Use docker compose cp to copy from container to host
        container_path = f"api:{output_path}"
        result = subprocess.run(
            ["docker", "compose", "cp", container_path, str(final_output_path)],
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✓ Copied to host: {final_output_path}")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Could not auto-copy. File is in container at: {output_path}")
        print(f"   Manually copy with: docker compose cp api:{output_path} data/{output_filename}")
    
    print(f"\n✅ Successfully created expiring soon PDF:")
    print(f"   {output_filename}")
    print(f"   Expiration date: {expiring_date.strftime('%B %d, %Y')} (expires in {60} days)")
    print(f"\n💡 Next steps:")
    print(f"   1. Upload this PDF via the Admin page")
    print(f"   2. Update term_months to match the expiration date")
    print(f"   3. Check if it's detected as 'expiring soon' in the Dashboard")


if __name__ == "__main__":
    main()

