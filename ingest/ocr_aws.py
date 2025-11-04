"""
AWS Textract OCR integration (for production use)
"""
from typing import List, Dict
import boto3
from botocore.exceptions import ClientError
import os


class AWSOCR:
    """AWS Textract-based OCR for production"""

    def __init__(self):
        region = os.getenv("AWS_REGION", "us-east-1")
        self.textract_client = boto3.client(
            'textract',
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )

    def ocr_pdf(self, pdf_path: str) -> List[Dict]:
        """
        Perform OCR on PDF using AWS Textract

        Args:
            pdf_path: Path to PDF file (local or S3 URI)

        Returns:
            List of dicts with 'page_num' and 'text' keys
        """
        try:
            # Check if it's an S3 path
            if pdf_path.startswith('s3://'):
                return self._ocr_s3_pdf(pdf_path)
            else:
                return self._ocr_local_pdf(pdf_path)
        except ClientError as e:
            raise Exception(f"Textract OCR failed: {e}")

    def _ocr_local_pdf(self, pdf_path: str) -> List[Dict]:
        """OCR local PDF file"""
        with open(pdf_path, 'rb') as file:
            pdf_bytes = file.read()

        response = self.textract_client.detect_document_text(
            Document={'Bytes': pdf_bytes}
        )

        # Extract text by page
        pages_text = {}
        current_text = []
        current_page = 1

        for block in response['Blocks']:
            if block['BlockType'] == 'PAGE':
                if current_text:
                    pages_text[current_page] = '\n'.join(current_text)
                    current_text = []
                current_page = block.get('Page', current_page)
            elif block['BlockType'] == 'LINE':
                current_text.append(block.get('Text', ''))

        # Add last page
        if current_text:
            pages_text[current_page] = '\n'.join(current_text)

        # Convert to list format
        ocr_results = [
            {'page_num': page_num, 'text': text}
            for page_num, text in pages_text.items()
        ]

        return ocr_results

    def _ocr_s3_pdf(self, s3_path: str) -> List[Dict]:
        """OCR PDF from S3"""
        # Parse S3 path: s3://bucket/key
        parts = s3_path.replace('s3://', '').split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''

        response = self.textract_client.detect_document_text(
            Document={
                'S3Object': {
                    'Bucket': bucket,
                    'Name': key
                }
            }
        )

        # Extract text by page (same as local)
        pages_text = {}
        current_text = []
        current_page = 1

        for block in response['Blocks']:
            if block['BlockType'] == 'PAGE':
                if current_text:
                    pages_text[current_page] = '\n'.join(current_text)
                    current_text = []
                current_page = block.get('Page', current_page)
            elif block['BlockType'] == 'LINE':
                current_text.append(block.get('Text', ''))

        if current_text:
            pages_text[current_page] = '\n'.join(current_text)

        ocr_results = [
            {'page_num': page_num, 'text': text}
            for page_num, text in pages_text.items()
        ]

        return ocr_results


# Global OCR instance (only initialized if USE_TEXTRACT=true)
aws_ocr = None

def get_aws_ocr():
    """Get AWS OCR instance if configured"""
    global aws_ocr
    if os.getenv("USE_TEXTRACT", "false").lower() == "true":
        if aws_ocr is None:
            aws_ocr = AWSOCR()
        return aws_ocr
    return None
