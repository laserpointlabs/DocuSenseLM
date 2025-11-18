"""
LLM Review Service for analyzing signed NDAs
"""
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from api.db import get_db_session
from api.db.schema import NDARecord, Document, DocumentStatus
from api.services.service_registry import get_storage_service

logger = logging.getLogger(__name__)


class LLMReviewService:
    """Service for reviewing NDAs using LLM"""

    def __init__(self):
        self.approval_threshold = float(os.getenv("WORKFLOW_LLM_APPROVAL_THRESHOLD", "0.7"))
        self.enabled = os.getenv("WORKFLOW_LLM_REVIEW_ENABLED", "true").lower() == "true"

    async def review_nda(self, nda_record_id: str) -> Dict[str, Any]:
        """
        Review an NDA using LLM and return approval/rejection decision
        
        Args:
            nda_record_id: UUID of the NDA record to review
            
        Returns:
            Dictionary with:
                - approved: bool
                - confidence: float (0.0-1.0)
                - reasoning: str
                - issues: List[str] (if any)
        """
        if not self.enabled:
            logger.info(f"LLM review disabled, auto-approving NDA {nda_record_id}")
            return {
                "approved": True,
                "confidence": 1.0,
                "reasoning": "LLM review is disabled",
                "issues": [],
            }

        db = get_db_session()
        try:
            import uuid
            nda_uuid = uuid.UUID(nda_record_id)
            nda_record = db.query(NDARecord).filter(NDARecord.id == nda_uuid).first()
            
            if not nda_record:
                raise ValueError(f"NDA record {nda_record_id} not found")
            
            # Get document text
            document_text = await self._get_document_text(nda_record)
            
            if not document_text:
                logger.warning(f"No text found for NDA {nda_record_id}, rejecting")
                return {
                    "approved": False,
                    "confidence": 0.0,
                    "reasoning": "No document text available for review",
                    "issues": ["Document text not available"],
                }
            
            # Perform LLM review
            review_result = await self._perform_llm_review(nda_record, document_text)
            
            logger.info(
                f"LLM review completed for NDA {nda_record_id}: "
                f"approved={review_result['approved']}, "
                f"confidence={review_result['confidence']}"
            )
            
            return review_result
            
        except Exception as e:
            logger.error(f"Failed to review NDA {nda_record_id}: {e}", exc_info=True)
            # On error, reject for safety
            return {
                "approved": False,
                "confidence": 0.0,
                "reasoning": f"Review failed: {str(e)}",
                "issues": [f"Review error: {str(e)}"],
            }
        finally:
            db.close()

    async def _get_document_text(self, nda_record: NDARecord) -> Optional[str]:
        """Extract text from NDA document"""
        try:
            # Try to get text from extracted_text field first
            if nda_record.extracted_text:
                return nda_record.extracted_text
            
            # If still no text, try to extract from file
            if nda_record.file_uri:
                storage = get_storage_service()
                try:
                    # Download file and extract text
                    import tempfile
                    import os
                    from ingest.parser import DocumentParser
                    
                    # Download file to temp location
                    file_bytes = storage.download_file(nda_record.file_uri)
                    if not file_bytes:
                        logger.warning(f"Could not download file from {nda_record.file_uri}")
                        return None
                    
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                        tmp_file.write(file_bytes)
                        tmp_path = tmp_file.name
                    
                    try:
                        # Extract text using DocumentParser
                        parser = DocumentParser()
                        result = parser.parse(tmp_path)
                        text = result.get('text', '')
                        
                        if text:
                            logger.info(f"Extracted {len(text)} characters from PDF file for NDA {nda_record.id}")
                            return text
                        else:
                            logger.warning(f"No text extracted from PDF file for NDA {nda_record.id}")
                            return None
                    finally:
                        # Clean up temp file
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                            
                except Exception as e:
                    logger.error(f"Failed to extract text from file: {e}", exc_info=True)
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting document text: {e}")
            return None

    async def _perform_llm_review(
        self,
        nda_record: NDARecord,
        document_text: str,
    ) -> Dict[str, Any]:
        """
        Perform actual LLM review of the NDA document
        
        This analyzes the NDA for:
        - Standard clauses and terms
        - Unusual or problematic language
        - Compliance with company policies
        - Risk assessment
        """
        try:
            # Import LLM client
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from llm.llm_factory import get_llm_client
            
            llm_client = get_llm_client()
            
            # Create review prompt
            prompt = self._create_review_prompt(nda_record, document_text)
            
            # Call LLM using direct API call (Ollama/OpenAI)
            # For now, use a simple async call to Ollama if available
            response = None
            try:
                if hasattr(llm_client, 'client') and hasattr(llm_client.client, 'post'):
                    # Ollama client - use direct API
                    import httpx
                    response_obj = await llm_client.client.post(
                        f"{llm_client.endpoint}/api/generate",
                        json={
                            "model": llm_client.model,
                            "prompt": prompt,
                            "stream": False,
                            "options": {"num_predict": 500}
                        },
                        timeout=60.0
                    )
                    if response_obj.status_code == 200:
                        response_data = response_obj.json()
                        response = response_data.get("response", "")
                    else:
                        logger.warning(f"Ollama API returned {response_obj.status_code}: {response_obj.text}")
                else:
                    # Fallback: use generate_answer with empty context
                    from llm.llm_client import Chunk, Citation
                    answer = await llm_client.generate_answer(
                        query=prompt,
                        context_chunks=[],
                        citations=[],
                    )
                    response = answer.text
            except Exception as e:
                logger.warning(f"LLM API call failed: {e}, using fallback review")
                response = None
            
            # If LLM call failed, use fallback review
            if not response:
                logger.info("LLM unavailable, using fallback review")
                return self._fallback_review(nda_record, document_text)
            
            # Parse LLM response
            review_result = self._parse_llm_response(response)
            
            # Determine approval based on confidence threshold
            approved = review_result["confidence"] >= self.approval_threshold
            
            return {
                "approved": approved,
                "confidence": review_result["confidence"],
                "reasoning": review_result.get("reasoning", ""),
                "issues": review_result.get("issues", []),
            }
            
        except Exception as e:
            logger.error(f"LLM review failed: {e}", exc_info=True)
            # Fallback: basic rule-based review
            return self._fallback_review(nda_record, document_text)

    def _create_review_prompt(self, nda_record: NDARecord, document_text: str) -> str:
        """Create prompt for LLM review"""
        prompt = f"""Review the following Non-Disclosure Agreement (NDA) and provide an assessment.

NDA Details:
- Counterparty: {nda_record.counterparty_name}
- Domain: {nda_record.counterparty_domain or 'N/A'}
- Effective Date: {nda_record.effective_date or 'N/A'}
- Term: {nda_record.term_months or 'N/A'} months

Document Text:
{document_text[:3000]}  # Limit text length

Please analyze this NDA and provide:
1. A confidence score (0.0 to 1.0) indicating how standard/acceptable this NDA is
2. A brief reasoning for your assessment
3. Any specific issues or concerns (if any)

Respond in JSON format:
{{
    "confidence": 0.85,
    "reasoning": "Brief explanation",
    "issues": ["Issue 1", "Issue 2"]
}}
"""
        return prompt

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured format"""
        import json
        import re
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return {
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "reasoning": parsed.get("reasoning", ""),
                    "issues": parsed.get("issues", []),
                }
        except Exception as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
        
        # Fallback: extract confidence from text
        confidence_match = re.search(r'confidence[:\s]+([0-9.]+)', response, re.IGNORECASE)
        confidence = float(confidence_match.group(1)) if confidence_match else 0.5
        
        return {
            "confidence": confidence,
            "reasoning": response[:200],  # First 200 chars
            "issues": [],
        }

    def _fallback_review(
        self,
        nda_record: NDARecord,
        document_text: str,
    ) -> Dict[str, Any]:
        """Fallback review when LLM is unavailable"""
        # Basic rule-based review
        issues = []
        confidence = 0.7  # Default moderate confidence
        
        # Check for basic NDA terms
        text_lower = document_text.lower()
        
        required_terms = ["confidential", "disclosure", "agreement"]
        missing_terms = [term for term in required_terms if term not in text_lower]
        
        if missing_terms:
            issues.append(f"Missing standard NDA terms: {', '.join(missing_terms)}")
            confidence -= 0.2
        
        # Check for unfilled template placeholders (major issue)
        import re
        placeholders = re.findall(r'\{[^}]+\}', document_text)
        if placeholders:
            unique_placeholders = list(set(placeholders))
            issues.append(f"Unfilled template placeholders found: {', '.join(unique_placeholders[:5])}")
            confidence -= 0.3  # Significant penalty for unfilled placeholders
        
        # Check document length (very short might be incomplete)
        if len(document_text) < 500:
            issues.append("Document appears to be very short")
            confidence -= 0.1
        
        # Check for unusual terms
        risky_terms = ["unlimited", "perpetual", "irrevocable"]
        found_risky = [term for term in risky_terms if term in text_lower]
        if found_risky:
            issues.append(f"Potentially risky terms found: {', '.join(found_risky)}")
            confidence -= 0.15
        
        confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1
        
        # When LLM is unavailable, use a lower threshold for fallback review
        # This prevents auto-rejection when LLM service is down
        fallback_threshold = min(self.approval_threshold, 0.6)
        
        return {
            "approved": confidence >= fallback_threshold,
            "confidence": confidence,
            "reasoning": f"Fallback rule-based review (LLM unavailable). Found {len(issues)} issue(s).",
            "issues": issues,
        }


# Global service instance
_llm_review_service: Optional[LLMReviewService] = None


def get_llm_review_service() -> LLMReviewService:
    """Get or create LLM review service instance"""
    global _llm_review_service
    if _llm_review_service is None:
        _llm_review_service = LLMReviewService()
    return _llm_review_service

