"""
Query normalization service
Handles misspellings, typos, variations, and poorly worded queries
"""
import re
from typing import Dict, List, Optional
from difflib import SequenceMatcher


class QueryNormalizer:
    """Service for normalizing and correcting queries"""
    
    def __init__(self):
        # Common misspellings and variations
        self.corrections = {
            # Legal terms
            'governing': ['governing', 'governing', 'governing'],
            'jurisdiction': ['jurisdiction', 'jurisdicition', 'juristiction'],
            'effective': ['effective', 'effecive', 'efective'],
            'effective date': ['effective data', 'effective date', 'effective dates'],  # Fix "data" -> "date"
            'date': ['date', 'data', 'dates'],  # Fix common typo "data" -> "date" when context suggests date
            'confidential': ['confidential', 'confidencial', 'confedential'],
            'disclosure': ['disclosure', 'disclosue', 'disclosre'],
            'agreement': ['agreement', 'agreemnt', 'agreemet'],
            'mutual': ['mutual', 'mutul', 'mutal'],
            'unilateral': ['unilateral', 'unilatral', 'unilaterl'],
            # Company suffixes
            'inc': ['inc', 'inc.', 'incorporated'],
            'llc': ['llc', 'l.l.c.', 'limited liability company'],
            'corp': ['corp', 'corp.', 'corporation'],
            # Date terms
            'january': ['january', 'jan', 'januray'],
            'february': ['february', 'feb', 'feburary'],
            'march': ['march', 'mar'],
            'april': ['april', 'apr'],
            'may': ['may'],
            'june': ['june', 'jun'],
            'july': ['july', 'jul'],
            'august': ['august', 'aug'],
            'september': ['september', 'sept', 'sep'],
            'october': ['october', 'oct'],
            'november': ['november', 'nov'],
            'december': ['december', 'dec'],
        }
        
        # Synonym mappings
        self.synonyms = {
            'governing state': ['governing law', 'jurisdiction', 'law applies'],
            'governing law': ['governing state', 'jurisdiction'],
            'term': ['duration', 'length', 'period', 'how long'],
            'effective date': ['date of agreement', 'signed date', 'when was', 'when did'],
            'parties': ['party to', 'who are', 'between', 'companies'],
            'mutual': ['mutual', 'both parties', 'two-way'],
            'unilateral': ['unilateral', 'one-way', 'one party'],
            'created': ['created', 'signed', 'executed', 'established', 'formed'],
            'in': ['in', 'during', 'from'],
        }
    
    def normalize_query(self, query: str) -> str:
        """
        Normalize query: fix common misspellings, expand abbreviations
        
        Args:
            query: Original query
            
        Returns:
            Normalized query
        """
        normalized = query
        
        # Fix multi-word phrases first (e.g., "effective data" -> "effective date")
        for correct, variations in self.corrections.items():
            if ' ' in correct:  # Multi-word phrase
                for variation in variations:
                    # Case-insensitive replacement for phrases
                    pattern = re.compile(re.escape(variation), re.IGNORECASE)
                    normalized = pattern.sub(correct, normalized)
        
        # Fix single-word misspellings
        for correct, variations in self.corrections.items():
            if ' ' not in correct:  # Single word only
                for variation in variations:
                    # Case-insensitive replacement
                    pattern = re.compile(r'\b' + re.escape(variation) + r'\b', re.IGNORECASE)
                    normalized = pattern.sub(correct, normalized)
        
        # Special case: Fix "effective data" -> "effective date" if not already fixed
        normalized = re.sub(r'\beffective\s+data\b', 'effective date', normalized, flags=re.IGNORECASE)
        # Fix standalone "data" when it appears in date-related contexts
        if any(term in normalized.lower() for term in ['effective', 'expiration', 'expiry', 'signed', 'date']):
            normalized = re.sub(r'\bdata\b', 'date', normalized, flags=re.IGNORECASE)
        
        return normalized
    
    def expand_synonyms(self, query: str) -> str:
        """
        Expand query with synonyms for better matching
        
        Args:
            query: Original query
            
        Returns:
            Query with synonyms added (only for relevant phrases, not every word)
        """
        query_lower = query.lower()
        expanded_terms = []
        
        # Check for multi-word phrases first and add their synonyms
        for phrase, synonyms in self.synonyms.items():
            if phrase in query_lower:
                # Add the original phrase and its synonyms
                expanded_terms.append(phrase)
                expanded_terms.extend(synonyms)
                # Remove the phrase from query_lower to avoid duplicate processing
                query_lower = query_lower.replace(phrase, '')
        
        # Add remaining words from original query (excluding already processed phrases)
        remaining_words = query.split()
        for word in remaining_words:
            word_lower = word.lower()
            # Only add if not already covered by a phrase
            if word_lower not in ' '.join(expanded_terms).lower():
                expanded_terms.append(word)
        
        return ' '.join(expanded_terms) if expanded_terms else query
    
    def fuzzy_match_company_name(self, query_name: str, target_name: str) -> float:
        """
        Calculate fuzzy match score between two company names
        
        Args:
            query_name: Company name from query
            target_name: Target company name to match against
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        query_lower = query_name.lower().strip()
        target_lower = target_name.lower().strip()
        
        # Exact match
        if query_lower == target_lower:
            return 1.0
        
        # Substring match (query is in target or vice versa)
        if query_lower in target_lower:
            # Boost score if query is at the start of target
            if target_lower.startswith(query_lower):
                return 0.95
            return 0.85
        if target_lower in query_lower:
            return 0.85
        
        # Check if query matches the first word of target (common for company names)
        # E.g., "Faunc" should match "Fanuc America Corporation"
        target_first_word = target_lower.split()[0] if target_lower.split() else ""
        query_first_word = query_lower.split()[0] if query_lower.split() else ""
        
        if target_first_word and query_first_word:
            # Check similarity of first words
            first_word_similarity = SequenceMatcher(None, query_first_word, target_first_word).ratio()
            if first_word_similarity >= 0.6:  # 60% similarity for first word
                # Boost score if first word matches well
                return 0.7 + (first_word_similarity * 0.2)  # 0.7 to 0.9 range
        
        # Word overlap
        query_words = set(query_lower.split())
        target_words = set(target_lower.split())
        if query_words and target_words:
            overlap = len(query_words & target_words)
            total = len(query_words | target_words)
            if total > 0:
                word_overlap_score = overlap / total
                # Also check sequence similarity
                seq_similarity = SequenceMatcher(None, query_lower, target_lower).ratio()
                # Check similarity of first words separately
                if target_first_word and query_first_word:
                    first_word_sim = SequenceMatcher(None, query_first_word, target_first_word).ratio()
                    # Combine all metrics, giving weight to first word match
                    combined = max(word_overlap_score, seq_similarity * 0.7, first_word_sim * 0.6)
                    return combined
                # Combine both metrics
                return max(word_overlap_score, seq_similarity * 0.8)
        
        # Sequence similarity as fallback
        return SequenceMatcher(None, query_lower, target_lower).ratio()
    
    def extract_date_range(self, query: str) -> Optional[Dict]:
        """
        Extract date range from query
        
        Examples:
            "NDAs created in January 2025" -> {"start": "2025-01-01", "end": "2025-01-31"}
            "agreements signed in 2025" -> {"start": "2025-01-01", "end": "2025-12-31"}
            "documents from January to March 2025" -> {"start": "2025-01-01", "end": "2025-03-31"}
        
        Args:
            query: User query
            
        Returns:
            Dict with start and end dates, or None
        """
        import re
        from datetime import datetime, timedelta
        
        query_lower = query.lower()
        
        # Month names
        months = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sept': 9, 'sep': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12,
        }
        
        # Pattern: "in January 2025" or "in Jan 2025"
        month_pattern = r'in\s+(' + '|'.join(months.keys()) + r')\s+(\d{4})'
        match = re.search(month_pattern, query_lower)
        if match:
            month_name = match.group(1)
            year = int(match.group(2))
            month_num = months[month_name]
            
            # Calculate start and end of month
            start_date = datetime(year, month_num, 1)
            if month_num == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(year, month_num + 1, 1) - timedelta(days=1)
            
            return {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            }
        
        # Pattern: "in 2025" (entire year)
        year_pattern = r'in\s+(\d{4})'
        match = re.search(year_pattern, query_lower)
        if match:
            year = int(match.group(1))
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31)
            
            return {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            }
        
        # Pattern: "from X to Y" or "between X and Y"
        range_pattern = r'(?:from|between)\s+(' + '|'.join(months.keys()) + r')\s+(?:to|and)\s+(' + '|'.join(months.keys()) + r')\s+(\d{4})'
        match = re.search(range_pattern, query_lower)
        if match:
            start_month_name = match.group(1)
            end_month_name = match.group(2)
            year = int(match.group(3))
            
            start_month = months[start_month_name]
            end_month = months[end_month_name]
            
            start_date = datetime(year, start_month, 1)
            if end_month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(year, end_month + 1, 1) - timedelta(days=1)
            
            return {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            }
        
        return None
    
    def reformulate_query(self, query: str) -> str:
        """
        Reformulate poorly worded queries to be more search-friendly
        
        Args:
            query: Original query (may be poorly worded)
            
        Returns:
            Reformulated query
        """
        query_lower = query.lower()
        
        # Fix common poorly worded patterns
        # "what nda where created" -> "NDAs created"
        query = re.sub(r'what\s+nda\s+where\s+created', 'NDAs created', query, flags=re.IGNORECASE)
        query = re.sub(r'what\s+ndas?\s+were?\s+created', 'NDAs created', query, flags=re.IGNORECASE)
        
        # "what is the governing state of X" -> "governing law X"
        query = re.sub(r'what\s+is\s+the\s+governing\s+state\s+of\s+', 'governing law ', query, flags=re.IGNORECASE)
        
        # Remove filler words that don't help search
        filler_words = ['can you tell me', 'i want to know', 'please tell me', 'i need to know']
        for filler in filler_words:
            query = re.sub(f'^{re.escape(filler)}\\s+', '', query, flags=re.IGNORECASE)
        
        return query.strip()


# Global instance
query_normalizer = QueryNormalizer()

