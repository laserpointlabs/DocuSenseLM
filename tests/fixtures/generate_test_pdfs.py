#!/usr/bin/env python3
"""
Generate fake test PDFs for testing.

These are fictional documents with no real company information.
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

# Output directory
FIXTURES_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(FIXTURES_DIR), "..", "data")


def create_fake_nda(filename: str, company_name: str, effective_date: str, expiration_date: str):
    """Create a fake NDA PDF."""
    filepath = os.path.join(DATA_DIR, filename)
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height - 1*inch, "NON-DISCLOSURE AGREEMENT")
    
    # Parties
    c.setFont("Helvetica", 12)
    y = height - 1.5*inch
    
    content = f"""
This Non-Disclosure Agreement ("Agreement") is entered into as of {effective_date}
("Effective Date") by and between:

{company_name} ("Disclosing Party")

and

ACME Test Corporation ("Receiving Party")

collectively referred to as the "Parties."

1. DEFINITION OF CONFIDENTIAL INFORMATION

"Confidential Information" means any and all non-public information, including but not 
limited to trade secrets, technical data, business plans, customer lists, financial 
information, and any other proprietary information disclosed by either party.

2. OBLIGATIONS OF RECEIVING PARTY

The Receiving Party agrees to:
(a) Hold and maintain the Confidential Information in strict confidence
(b) Not disclose the Confidential Information to any third parties
(c) Use the Confidential Information solely for the purposes of this Agreement
(d) Protect the Confidential Information using reasonable security measures

3. TERM AND TERMINATION

This Agreement shall remain in effect for a period of three (3) years from the
Effective Date, expiring on {expiration_date}, unless terminated earlier by
written agreement of both Parties.

4. JURISDICTION

This Agreement shall be governed by the laws of the State of Delaware, USA.

5. CONFIDENTIALITY PERIOD

The obligations of confidentiality shall survive for a period of five (5) years
following the expiration or termination of this Agreement.

IN WITNESS WHEREOF, the Parties have executed this Agreement as of the date
first written above.


_________________________                    _________________________
{company_name}                               ACME Test Corporation
Authorized Signature                         Authorized Signature

Date: {effective_date}                       Date: {effective_date}
"""
    
    # Draw the content
    text_object = c.beginText(0.75*inch, y)
    text_object.setFont("Helvetica", 10)
    for line in content.strip().split('\n'):
        text_object.textLine(line)
    c.drawText(text_object)
    
    c.save()
    print(f"Created: {filepath}")
    return filepath


def create_fake_service_agreement(filename: str, company_name: str, service_type: str, 
                                   contract_price: str, effective_date: str, expiration_date: str):
    """Create a fake service agreement PDF."""
    filepath = os.path.join(DATA_DIR, filename)
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height - 1*inch, f"{service_type.upper()} SERVICE AGREEMENT")
    
    y = height - 1.5*inch
    
    content = f"""
This Service Agreement ("Agreement") is entered into as of {effective_date}
by and between:

{company_name} ("Service Provider")

and

ACME Test Corporation ("Client")

1. SERVICES

The Service Provider agrees to provide the following services:
- Monthly {service_type.lower()} maintenance
- Quarterly inspections
- Emergency response within 24 hours
- Annual comprehensive review

2. COMPENSATION

The Client agrees to pay the Service Provider:

Seasonal Contract Price: {contract_price}

Payment Terms: Net 30 days from invoice date.

Additional services not covered under this agreement shall be billed at:
- Standard hourly rate: $75.00 per hour
- Emergency rate: $125.00 per hour
- Materials: Cost plus 15%

3. TERM

This Agreement shall be effective from {effective_date} through {expiration_date}.

4. TERMINATION

Either party may terminate this Agreement with 30 days written notice.

5. LIABILITY

The Service Provider shall maintain appropriate insurance coverage and shall 
be liable for damages caused by negligence in the performance of services.


_________________________                    _________________________
{company_name}                               ACME Test Corporation
Authorized Signature                         Authorized Signature

Date: {effective_date}                       Date: {effective_date}
"""
    
    text_object = c.beginText(0.75*inch, y)
    text_object.setFont("Helvetica", 10)
    for line in content.strip().split('\n'):
        text_object.textLine(line)
    c.drawText(text_object)
    
    c.save()
    print(f"Created: {filepath}")
    return filepath


def main():
    """Generate all test PDFs."""
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Create fake Green NDA (used by test_lite_e2e.py and test_llm_efficacy.py)
    create_fake_nda(
        filename="green_nda.pdf",
        company_name="Green Leaf Technologies, Inc.",
        effective_date="January 15, 2025",
        expiration_date="January 15, 2028"
    )
    
    # Create a second fake NDA for variety
    create_fake_nda(
        filename="blue_nda.pdf", 
        company_name="Blue Ocean Enterprises, LLC",
        effective_date="March 1, 2025",
        expiration_date="March 1, 2028"
    )
    
    # Create a fake service agreement
    create_fake_service_agreement(
        filename="test_service_agreement.pdf",
        company_name="Sunshine Facilities Management",
        service_type="Facility Maintenance",
        contract_price="$24,000.00 annually",
        effective_date="February 1, 2025",
        expiration_date="January 31, 2026"
    )
    
    print("\nAll test PDFs generated successfully!")


if __name__ == "__main__":
    main()
