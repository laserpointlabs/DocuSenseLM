"""
Document finder service - finds documents by company name or other criteria
Enables flexible queries without requiring exact document IDs
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from typing import List, Optional, Dict
from api.db import get_db_session
from api.db.schema import Document, Party, DocumentMetadata, DocumentStatus
import uuid
import re
from api.services.query_normalizer import query_normalizer


class DocumentFinder:
    """Service for finding documents by company name or other criteria"""
    
    def find_documents_by_company_name(self, company_name: str, use_fuzzy: bool = True) -> List[Dict]:
        """
        Find documents by company name (searches Party names and document filenames)
        Uses fuzzy matching for better flexibility with misspellings
        
        Args:
            company_name: Company name (can be partial, e.g., "Vallen")
            use_fuzzy: Whether to use fuzzy matching for better results
            
        Returns:
            List of document info dicts with id, filename, and match confidence
        """
        db = get_db_session()
        try:
            company_name_lower = company_name.lower().strip()
            
            # Get all parties and documents for fuzzy matching
            all_parties = db.query(Party).all()
            all_documents = db.query(Document).filter(
                Document.status == DocumentStatus.PROCESSED
            ).all()
            
            found_docs = {}
            
            if use_fuzzy:
                # Use fuzzy matching for better flexibility
                for party in all_parties:
                    party_name = party.party_name
                    if not party_name:
                        continue
                    
                    # Calculate fuzzy match score
                    similarity = query_normalizer.fuzzy_match_company_name(company_name, party_name)
                    
                    # Threshold for fuzzy matching (0.3 = 30% similarity)
                    if similarity >= 0.3:
                        doc_id = str(party.document_id)
                        if doc_id not in found_docs or similarity > found_docs[doc_id]["confidence"]:
                            doc = db.query(Document).filter(Document.id == party.document_id).first()
                            if doc and doc.status == DocumentStatus.PROCESSED:
                                found_docs[doc_id] = {
                                    "document_id": doc_id,
                                    "filename": doc.filename,
                                    "match_type": "party_name_fuzzy",
                                    "match_value": party_name,
                                    "confidence": similarity
                                }
                
                # Also check filenames with fuzzy matching
                for doc in all_documents:
                    doc_id = str(doc.id)
                    if doc_id not in found_docs:
                        similarity = query_normalizer.fuzzy_match_company_name(company_name, doc.filename)
                        if similarity >= 0.3:
                            found_docs[doc_id] = {
                                "document_id": doc_id,
                                "filename": doc.filename,
                                "match_type": "filename_fuzzy",
                                "match_value": doc.filename,
                                "confidence": similarity
                            }
            else:
                # Exact/partial matching (original behavior)
                # Search in Party names
                parties = db.query(Party).filter(
                    Party.party_name.ilike(f"%{company_name}%")
                ).all()
                
                # Search in document filenames
                documents = db.query(Document).filter(
                    Document.filename.ilike(f"%{company_name}%"),
                    Document.status == DocumentStatus.PROCESSED
                ).all()
                
                # Add documents from party matches
                for party in parties:
                    doc_id = str(party.document_id)
                    if doc_id not in found_docs:
                        doc = db.query(Document).filter(Document.id == party.document_id).first()
                        if doc and doc.status == DocumentStatus.PROCESSED:
                            party_name_lower = party.party_name.lower()
                            if company_name_lower == party_name_lower:
                                confidence = 1.0
                            elif company_name_lower in party_name_lower:
                                confidence = 0.8
                            else:
                                confidence = 0.6
                            
                            found_docs[doc_id] = {
                                "document_id": doc_id,
                                "filename": doc.filename,
                                "match_type": "party_name",
                                "match_value": party.party_name,
                                "confidence": confidence
                            }
                
                # Add documents from filename matches
                for doc in documents:
                    doc_id = str(doc.id)
                    if doc_id not in found_docs:
                        filename_lower = doc.filename.lower()
                        if company_name_lower == filename_lower:
                            confidence = 1.0
                        elif filename_lower.startswith(company_name_lower):
                            confidence = 0.9
                        else:
                            confidence = 0.7
                        
                        found_docs[doc_id] = {
                            "document_id": doc_id,
                            "filename": doc.filename,
                            "match_type": "filename",
                            "match_value": doc.filename,
                            "confidence": confidence
                        }
            
            # Sort by confidence (highest first)
            results = list(found_docs.values())
            results.sort(key=lambda x: x["confidence"], reverse=True)
            
            return results
        finally:
            db.close()
    
    def extract_company_name_from_query(self, query: str) -> Optional[str]:
        """
        Extract company name from query
        
        Examples:
            "What is the governing state of Vallen Industries?" -> "Vallen Industries"
            "What is the governing state of Vallen?" -> "Vallen"
            "What is the term for Acme Corp?" -> "Acme Corp"
            "Who are the parties to the KGS NDA?" -> "KGS"
        """
        query_lower = query.lower()
        
        # Skip words that are not company names
        skip_words = {'what', 'is', 'the', 'for', 'of', 'with', 'governing', 'state', 'law', 'term', 
                     'date', 'parties', 'to', 'who', 'are', 'nda', 'agreement', 'does', 'specify',
                     'clause', 'effective', 'duration', 'how', 'long', 'expires', 'expiration'}
        
        # Pattern 1: "of X" or "for X" where X is a company name
        patterns = [
            r'(?:of|for|with)\s+([A-Z][A-Za-z&\-\s]+?(?:\s+(?:Industries|Distribution|Corporation|Company|LLC|Inc\.|Ltd\.|Limited|Corp))?)',
            r'(?:of|for|with)\s+([A-Z][A-Za-z&\-\s]{3,})(?:\s+(?:NDA|agreement|clause))?',
            r'(?:of|for|with)\s+([A-Z][A-Za-z]{2,})',  # Simple pattern: "of Vallen" -> "Vallen"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                company_name = match.group(1).strip()
                # Clean up common suffixes/prefixes
                company_name = re.sub(r'\s+(the|a|an)\s+', ' ', company_name, flags=re.IGNORECASE)
                company_name = company_name.strip()
                # Remove trailing question marks, periods
                company_name = company_name.rstrip('?.,')
                if len(company_name) > 2:  # Minimum length
                    return company_name
        
        # Fallback: look for capitalized words that might be company names
        words = query.split()
        capitalized_words = []
        for i, word in enumerate(words):
            # Remove punctuation
            clean_word = word.rstrip('?.,')
            # Check if word starts with capital (or is all caps like FANUC)
            is_capitalized = (clean_word and clean_word[0].isupper()) or (clean_word and clean_word.isupper() and len(clean_word) > 1)
            if is_capitalized and len(clean_word) > 1:
                # Skip common question words and legal terms
                if clean_word.lower() not in skip_words:
                    capitalized_words.append(clean_word)
                    # If next word is also capitalized and not a skip word, include it
                    if i + 1 < len(words):
                        next_word = words[i + 1].rstrip('?.,')
                        next_is_capitalized = (next_word and next_word[0].isupper()) or (next_word and next_word.isupper() and len(next_word) > 1)
                        if next_is_capitalized and next_word.lower() not in skip_words:
                            capitalized_words.append(next_word)
                            break
        
        if capitalized_words:
            return ' '.join(capitalized_words)
        
        return None
    
    def find_best_document_match(self, query: str, use_fuzzy: bool = True) -> Optional[str]:
        """
        Find the best matching document ID for a query
        Uses fuzzy matching by default for better flexibility
        
        For location queries, prioritizes documents with corporate office addresses
        
        Args:
            query: User query
            use_fuzzy: Whether to use fuzzy matching (default: True)
            
        Returns:
            Best matching document_id or None
        """
        company_name = self.extract_company_name_from_query(query)
        if not company_name:
            return None
        
        matches = self.find_documents_by_company_name(company_name, use_fuzzy=use_fuzzy)
        if not matches:
            return None
        
        # Check if this is a location query
        query_lower = query.lower()
        is_location_query = any(term in query_lower for term in ['where', 'located', 'address', 'location', 'office'])
        
        if is_location_query and len(matches) > 1:
            # For location queries with multiple matches, prioritize documents with corporate office
            # Check each document for corporate office address
            from api.db import get_db_session
            from api.db.schema import DocumentChunk
            import re
            
            db = get_db_session()
            try:
                best_match = None
                best_score = 0
                
                for match in matches:
                    doc_id = match["document_id"]
                    # Search for corporate office indicators
                    chunks = db.query(DocumentChunk).filter(
                        DocumentChunk.document_id == doc_id
                    ).limit(20).all()
                    
                    score = match["confidence"]
                    for chunk in chunks:
                        text = chunk.text.lower()
                        # Boost score if corporate office or headquarters is mentioned
                        # (without hardcoding specific addresses)
                        if 'corporate office' in text or 'headquarters' in text or 'head office' in text:
                            score += 0.3  # Moderate boost for corporate office/headquarters mention
                            break
                    
                    if score > best_score:
                        best_score = score
                        best_match = match
                
                if best_match and best_match["confidence"] >= 0.3:
                    return best_match["document_id"]
            finally:
                db.close()
        
        # Default: return highest confidence match (deterministic by sorting)
        best_match = matches[0]
        if best_match["confidence"] >= 0.3:
            return best_match["document_id"]
        
        return None


# Global instance
document_finder = DocumentFinder()
