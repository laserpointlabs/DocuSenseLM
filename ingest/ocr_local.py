"""
Local OCR using Tesseract
"""
from typing import List, Dict
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import os


class LocalOCR:
    """Tesseract-based OCR for local development"""

    def __init__(self):
        # Check if Tesseract is available
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            raise Exception(f"Tesseract not found. Please install Tesseract OCR: {e}")

    def ocr_pages(self, pdf_path: str, page_nums: List[int] = None) -> List[Dict]:
        """
        Perform OCR on PDF pages

        Args:
            pdf_path: Path to PDF file
            page_nums: List of page numbers to OCR (1-indexed). If None, OCR all pages.

        Returns:
            List of dicts with 'page_num' and 'text' keys
        """
        try:
            # Convert PDF pages to images
            images = convert_from_path(pdf_path)

            ocr_results = []

            for idx, image in enumerate(images):
                page_num = idx + 1

                # Skip if page_nums specified and this page not in list
                if page_nums and page_num not in page_nums:
                    continue

                # Perform OCR
                text = pytesseract.image_to_string(image, lang='eng')

                ocr_results.append({
                    'page_num': page_num,
                    'text': text
                })

            return ocr_results
        except Exception as e:
            raise Exception(f"OCR failed: {e}")

    def ocr_image(self, image_path: str) -> str:
        """
        Perform OCR on a single image

        Args:
            image_path: Path to image file

        Returns:
            Extracted text
        """
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang='eng')
            return text
        except Exception as e:
            raise Exception(f"OCR failed for image: {e}")


# Global OCR instance
local_ocr = LocalOCR()
