"""
OCR detection: determine if a document needs OCR
"""
from typing import Dict, List


class OCRDetector:
    """Detect if document pages need OCR"""

    def needs_ocr(self, parsed_pages: List[Dict]) -> bool:
        """
        Determine if document needs OCR based on parsed pages

        Args:
            parsed_pages: List of page dicts with 'text' and 'is_scanned' keys

        Returns:
            True if any page needs OCR
        """
        # Check if any page is marked as scanned or has very little text
        for page in parsed_pages:
            if page.get('is_scanned', False):
                return True

            # If page has less than 100 characters, likely needs OCR
            text = page.get('text', '')
            if len(text.strip()) < 100:
                return True

        return False

    def get_pages_needing_ocr(self, parsed_pages: List[Dict]) -> List[int]:
        """
        Get list of page numbers that need OCR

        Returns:
            List of page numbers (1-indexed)
        """
        pages_needing_ocr = []

        for page in parsed_pages:
            page_num = page.get('page_num', 0)
            is_scanned = page.get('is_scanned', False)
            text = page.get('text', '')

            if is_scanned or len(text.strip()) < 100:
                pages_needing_ocr.append(page_num)

        return pages_needing_ocr


# Global detector instance
ocr_detector = OCRDetector()
