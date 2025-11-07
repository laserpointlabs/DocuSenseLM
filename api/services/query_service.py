"""
Query understanding and transformation service
Detects question types, expands queries, and transforms for better retrieval
"""
from typing import Dict, Optional, Tuple
from api.services.query_normalizer import query_normalizer


class QueryService:
    """Service for query understanding and transformation"""

    def __init__(self):
        # Query expansion mappings
        self.expansion_map = {
            'governing': ['governing law', 'governing state', 'jurisdiction', 'law applies'],
            'term': ['term', 'duration', 'how long', 'expires', 'expiration', 'length'],
            'date': ['effective date', 'date of agreement', 'signed date', 'when was', 'when did'],
            'mutual': ['mutual', 'unilateral', 'is the', 'type of'],
            'parties': ['parties', 'party to', 'who are', 'between'],
        }

    def detect_question_type(self, question: str) -> Tuple[str, Dict]:
        """
        Detect question type and extract metadata
        
        Args:
            question: User question
            
        Returns:
            Tuple of (question_type, metadata_dict)
        """
        # Normalize query first (fix misspellings, etc.)
        normalized_question = query_normalizer.normalize_query(question)
        question_lower = normalized_question.lower()
        
        # Check for date-based queries (e.g., "NDAs created in January 2025")
        date_range = query_normalizer.extract_date_range(question)
        if date_range:
            return ("date_range", {"is_date_range": True, "date_range": date_range})
        
        # Check for cross-document queries
        if any(term in question_lower for term in ['compare', 'across all', 'all ndas', 'all documents', 'difference', 'different']):
            return ("cross_document", {"is_cross_document": True})
        
        # Check for structured questions
        # Check expiration date FIRST (before effective date, as "expire" might match "effective")
        if any(term in question_lower for term in ['expire', 'expiration date', 'expiry date', 'expires', 'when does it expire']):
            return ("structured", {"field": "expiration_date", "is_structured": True})
        
        if any(term in question_lower for term in ['effective date', 'date of agreement', 'signed date', 'when was', 'when did']):
            return ("structured", {"field": "effective_date", "is_structured": True})
        
        elif any(term in question_lower for term in ['governing law', 'governing state', 'jurisdiction', 'law applies', 'what law']):
            return ("structured", {"field": "governing_law", "is_structured": True})
        
        elif any(term in question_lower for term in ['term', 'duration', 'how long', 'expires', 'expiration', 'length', 'expire', 'when does it expire', 'expiry date']):
            if 'survival' not in question_lower and 'after' not in question_lower:
                return ("structured", {"field": "term", "is_structured": True})
        
        elif any(term in question_lower for term in ['mutual', 'unilateral', 'is the', 'type of']):
            return ("structured", {"field": "is_mutual", "is_structured": True})
        
        elif any(term in question_lower for term in ['parties', 'party to', 'who are', 'between']):
            return ("structured", {"field": "parties", "is_structured": True})
        
        # Check for clause-specific questions - extract clause name
        elif any(term in question_lower for term in ['clause', 'specify', 'definition', 'protection', 'non-disclosure', 'non disclosure']):
            clause_name = self._extract_clause_name(question)
            return ("clause", {"is_clause_specific": True, "clause_name": clause_name})
        
        # Default to general
        return ("general", {"is_general": True})
    
    def _extract_clause_name(self, question: str) -> Optional[str]:
        """
        Extract clause name from question
        
        Examples:
            "What does the Definition clause specify" -> "Definition"
            "What does the Non-Disclosure clause specify" -> "Non-Disclosure"
            "What does the Protection of Confidential Information clause specify" -> "Protection of Confidential Information"
        """
        import re
        question_lower = question.lower()
        
        # Pattern: "the X clause" or "the X clause specify"
        patterns = [
            r'the\s+([^c]+?)\s+clause',  # "the Definition clause"
            r'what does the\s+([^c]+?)\s+clause',  # "what does the Definition clause"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question_lower)
            if match:
                clause_name = match.group(1).strip()
                # Clean up common prefixes/suffixes
                clause_name = re.sub(r'^(the|a|an)\s+', '', clause_name, flags=re.IGNORECASE)
                if clause_name and len(clause_name) > 2:
                    # Capitalize first letter of each word
                    return ' '.join(word.capitalize() for word in clause_name.split())
        
        # Fallback: look for common clause keywords
        clause_keywords = {
            'definition': 'Definition',
            'non-disclosure': 'Non-Disclosure',
            'non disclosure': 'Non-Disclosure',
            'protection of confidential': 'Protection of Confidential Information',
            'protection': 'Protection',
            'confidential information': 'Confidential Information',
            'obligation': 'Obligation',
            'term': 'Term',
            'survival': 'Survival',
            'governing law': 'Governing Law',
        }
        
        for keyword, clause_name in clause_keywords.items():
            if keyword in question_lower:
                return clause_name
        
        return None

    def expand_query(self, question: str, question_type: str) -> str:
        """
        Expand query with synonyms and related terms for better retrieval
        
        Args:
            question: Original question
            question_type: Detected question type
            
        Returns:
            Expanded query
        """
        question_lower = question.lower()
        expanded_question = question
        
        # For governing law questions, expand with synonyms
        if 'governing' in question_lower or 'jurisdiction' in question_lower:
            # Add "governing law" if only "governing state" is present
            if 'governing state' in question_lower and 'governing law' not in question_lower:
                expanded_question = expanded_question.replace('governing state', 'governing state governing law')
            elif 'governing law' not in question_lower:
                expanded_question = f"{expanded_question} governing law"
        
        # For term questions, add synonyms
        if 'term' in question_lower or 'duration' in question_lower:
            if 'term' not in question_lower:
                expanded_question = f"{expanded_question} term"
            if 'duration' not in question_lower:
                expanded_question = f"{expanded_question} duration"
        
        return expanded_question

    def transform_query_for_retrieval(self, question: str, question_type: str, metadata: Dict = None) -> str:
        """
        Transform query for better retrieval
        
        Args:
            question: Original question
            question_type: Detected question type
            metadata: Query metadata (may contain clause_name)
            
        Returns:
            Transformed query optimized for retrieval
        """
        question_lower = question.lower()
        
        # Transform "governing state of X" -> "governing law X" for better retrieval
        if 'governing state' in question_lower:
            question = question.replace('governing state', 'governing law')
            question = question.replace('Governing State', 'Governing Law')
        
        # Transform "what is the term" -> "term duration" for better chunk matching
        if 'what is the term' in question_lower:
            question = question.replace('what is the term', 'term duration')
            question = question.replace('What is the term', 'Term duration')
        
        # For clause questions, enhance with clause-specific terms
        if question_type == "clause" and metadata and metadata.get('clause_name'):
            clause_name = metadata.get('clause_name')
            clause_lower = clause_name.lower()
            
            # Remove question words and focus on clause content
            # "What does the X clause specify" -> "X clause specifies terms conditions"
            question = question.replace('what does the', '').replace('clause specify', '').replace('clause', '').strip()
            
            # Add clause name and related terms
            clause_terms = [clause_name]
            
            # Add synonyms and related terms based on clause type
            if 'definition' in clause_lower:
                clause_terms.extend(['definition', 'defines', 'means', 'shall mean', 'confidential information'])
            elif 'non-disclosure' in clause_lower or 'non disclosure' in clause_lower:
                clause_terms.extend(['non-disclosure', 'disclosure', 'shall not disclose', 'recipient', 'confidential'])
            elif 'protection' in clause_lower or 'confidential' in clause_lower:
                clause_terms.extend(['protection', 'confidential information', 'protect', 'safeguard', 'security'])
            elif 'obligation' in clause_lower:
                clause_terms.extend(['obligation', 'duty', 'shall', 'must', 'required'])
            
            # Reconstruct query with clause terms
            question = f"{' '.join(clause_terms)} {question}".strip()
        
        return question

    def understand_query(self, question: str) -> Dict:
        """
        Complete query understanding: detect type, expand, and transform
        
        Args:
            question: User question
            
        Returns:
            Dict with query_type, metadata, expanded_query, transformed_query
        """
        # Step 1: Normalize query (fix misspellings, reformulate)
        normalized_query = query_normalizer.normalize_query(question)
        reformulated_query = query_normalizer.reformulate_query(normalized_query)
        
        # Step 2: Detect question type
        question_type, metadata = self.detect_question_type(reformulated_query)
        
        # Step 3: Expand with synonyms (but don't over-expand)
        expanded_query = self.expand_query(reformulated_query, question_type)
        # Only expand synonyms if it's a general question (structured questions already have good keywords)
        if question_type != "structured":
            expanded_query = query_normalizer.expand_synonyms(expanded_query)
        
        # Step 4: Transform for retrieval
        transformed_query = self.transform_query_for_retrieval(expanded_query, question_type, metadata)
        
        return {
            "original_query": question,
            "normalized_query": normalized_query,
            "reformulated_query": reformulated_query,
            "question_type": question_type,
            "metadata": metadata,
            "expanded_query": expanded_query,
            "transformed_query": transformed_query
        }


# Global service instance
query_service = QueryService()

