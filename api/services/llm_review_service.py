"""
LLM Review Service for analyzing NDAs

Stub implementation for Phase 1 - will be fully implemented in Phase 5
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class LLMReviewService:
    """Service for reviewing NDAs using LLM (stub implementation)"""

    def __init__(self):
        self.enabled = True  # For Phase 1, always enabled

    async def review_nda(self, nda_record_id: str) -> Dict[str, Any]:
        """
        Review an NDA using LLM (stub implementation)
        
        Returns basic approval for Phase 1 testing
        """
        logger.info(f"LLM review requested for NDA {nda_record_id} (stub implementation)")
        
        return {
            "approved": True,
            "confidence": 0.8,
            "reasoning": "Phase 1 stub implementation - auto-approved",
            "issues": []
        }


# Global service instance
_llm_review_service: Optional[LLMReviewService] = None


def get_llm_review_service() -> LLMReviewService:
    """Get or create LLM review service instance"""
    global _llm_review_service
    if _llm_review_service is None:
        _llm_review_service = LLMReviewService()
    return _llm_review_service