"""
Clause extractor for NDA documents
Parses sections: title, recitals (WHEREAS), numbered clauses, signature block
Extracts metadata: parties, dates, governing law
"""
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dateutil import parser as date_parser


class ClauseExtractor:
    """Extract clauses and metadata from NDA text"""

    def __init__(self):
        # Patterns for common NDA structures
        # Note: These patterns match the clause number/prefix, not the full title
        self.clause_patterns = [
            r'^\s*(\d+[\.\)]?\s+)',  # "1. " or "1) " - matches number and separator
            r'^\s*(\d+\.\d+\.?\s+)',  # "1.1. " - matches sub-clause
            r'^\s*(\d+\.\d+\.\d+\.?\s+)',  # "1.1.1. " - matches sub-sub-clause
        ]
        # Pattern for clause headers (all caps with colon)
        self.clause_header_pattern = r'^\s*([A-Z][A-Z\s]+:)'

        # Recital patterns
        self.recital_patterns = [
            r'^\s*WHEREAS',
            r'^\s*RECITAL',
            r'^\s*BACKGROUND',
        ]

        # Party patterns
        self.party_patterns = [
            r'(?:Disclosing|Discloser)\s+Party[:\s]+([A-Z][^\n,]+)',
            r'(?:Receiving|Recipient)\s+Party[:\s]+([A-Z][^\n,]+)',
            r'between\s+([A-Z][^\n,]+)\s+and\s+([A-Z][^\n,]+)',
            r'([A-Z][A-Z\s&]+(?:Inc\.|LLC|Corp\.|Ltd\.|Company))',
        ]

        # Date patterns
        self.date_patterns = [
            r'(?:Effective|Dated?|Date)\s+(?:Date\s+of\s+)?([A-Z][a-z]+ \d{1,2}, \d{4})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})',
        ]

        # Governing law patterns
        self.governing_law_patterns = [
            r'governed?\s+by\s+the\s+laws?\s+of\s+([A-Z][^\n,\.]+)',
            r'construed?\s+in\s+accordance\s+with\s+the\s+laws?\s+of\s+([A-Z][^\n,\.]+)',
            r'jurisdiction[:\s]+([A-Z][^\n,\.]+)',
        ]

        # Term patterns
        self.term_patterns = [
            r'term\s+of\s+(\d+)\s+(?:months?|years?)',
            r'period\s+of\s+(\d+)\s+(?:months?|years?)',
            r'expires?\s+(?:on|after)\s+(\d+)\s+(?:months?|years?)',
        ]

        # Survival patterns
        self.survival_patterns = [
            r'survive\s+(?:for\s+)?(\d+)\s+(?:months?|years?)',
            r'survival\s+period\s+of\s+(\d+)\s+(?:months?|years?)',
        ]

    def extract(self, text: str, pages: List[Dict]) -> Dict:
        """
        Extract clauses and metadata from document text

        Args:
            text: Full document text
            pages: List of page dicts with 'page_num' and 'text'

        Returns:
            Dict with keys: title, recitals, clauses, metadata
        """
        # Extract title (usually first line or first paragraph)
        title = self._extract_title(text)

        # Extract recitals (WHEREAS clauses)
        recitals = self._extract_recitals(text, pages)

        # Extract numbered clauses
        clauses = self._extract_clauses(text, pages)

        # Extract metadata
        metadata = self._extract_metadata(text)

        return {
            'title': title,
            'recitals': recitals,
            'clauses': clauses,
            'metadata': metadata
        }

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract document title"""
        lines = text.split('\n')[:10]  # Check first 10 lines
        for line in lines:
            line = line.strip()
            if line and len(line) > 10 and len(line) < 200:
                # Check if it looks like a title
                if any(keyword in line.upper() for keyword in ['NDA', 'AGREEMENT', 'DISCLOSURE', 'CONFIDENTIALITY']):
                    return line
        return None

    def _extract_recitals(self, text: str, pages: List[Dict]) -> List[Dict]:
        """Extract WHEREAS/recital clauses"""
        recitals = []
        lines = text.split('\n')
        current_recital = None
        current_page = 1

        for i, line in enumerate(lines):
            # Determine which page this line is on
            char_pos = sum(len(l) + 1 for l in lines[:i])
            for page in pages:
                if char_pos >= page.get('span_start', 0) and char_pos <= page.get('span_end', len(text)):
                    current_page = page['page_num']
                    break

            # Check if line starts a recital
            for pattern in self.recital_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    if current_recital:
                        recitals.append(current_recital)
                    current_recital = {
                        'text': line,
                        'page_num': current_page,
                        'clause_number': f"WHEREAS-{len(recitals) + 1}"
                    }
                    break

            # Continue building current recital
            if current_recital:
                if line.strip():
                    current_recital['text'] += ' ' + line.strip()
                # End recital on blank line or next section
                elif len(current_recital['text']) > 100:
                    recitals.append(current_recital)
                    current_recital = None

        if current_recital:
            recitals.append(current_recital)

        return recitals

    def _extract_clauses(self, text: str, pages: List[Dict]) -> List[Dict]:
        """Extract numbered clauses with better title extraction"""
        clauses = []
        lines = text.split('\n')
        current_clause = None
        current_page = 1
        title_lines_collected = 0  # Track how many lines we've collected for title

        for i, line in enumerate(lines):
            # Determine which page this line is on
            char_pos = sum(len(l) + 1 for l in lines[:i])
            for page in pages:
                if char_pos >= page.get('span_start', 0) and char_pos <= page.get('span_end', len(text)):
                    current_page = page['page_num']
                    break

            # Check if line starts a clause
            clause_number = None
            clause_title = None

            # Try numbered clause patterns first
            for pattern in self.clause_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    clause_number = match.group(1).strip().rstrip('.')  # Remove trailing period from number
                    # Extract everything after the number prefix
                    remaining = line[len(match.group(0)):].strip()

                    # Extract title - look for pattern like "Title .  " or "Title."
                    # The title typically ends with a period followed by spaces
                    # Pattern: word(s) followed by optional period and spaces
                    title_match = re.match(r'^([A-Z][A-Za-z\s-]+?)\s*\.\s+', remaining)
                    if title_match:
                        clause_title = title_match.group(1).strip()
                    else:
                        # Try splitting on period - title is usually before first period
                        parts = remaining.split('.', 1)
                        if len(parts) > 1 and parts[0].strip():
                            clause_title = parts[0].strip()
                            # If title is just one letter, it's likely incomplete
                            # Try to get more from the next part
                            if len(clause_title) == 1 and clause_title[0].isupper():
                                next_part = parts[1].strip()
                                words = next_part.split()
                                if words:
                                    # Get the full word that starts with this letter
                                    first_word = words[0]
                                    if first_word[0].lower() == clause_title.lower():
                                        clause_title = first_word.rstrip('.')
                                    else:
                                        # Just take the first capitalized word
                                        clause_title = first_word.rstrip('.')
                        else:
                            # No period found, take first capitalized word/phrase
                            words = remaining.split()
                            if words and words[0][0].isupper():
                                clause_title = words[0].rstrip('.')
                                # Add more capitalized words up to reasonable length
                                for word in words[1:5]:  # Allow up to 5 words
                                    if word[0].isupper() and '.' not in word and len(clause_title + ' ' + word) < 50:
                                        clause_title += ' ' + word
                                    else:
                                        break

                    # Clean up title - remove extra spaces, hyphens at start/end
                    if clause_title:
                        clause_title = re.sub(r'\s+', ' ', clause_title).strip()
                        clause_title = clause_title.strip('-').strip()

                        # If title is still too short (1-2 chars), try looking ahead
                        if len(clause_title) <= 2 and clause_title[0].isupper():
                            # Look ahead up to 3 lines for the full word
                            for j in range(1, min(4, len(lines) - i)):
                                if i + j < len(lines):
                                    next_line = lines[i + j].strip()
                                    # Stop if we hit another clause
                                    if re.match(r'^\s*\d+[\.\)]', next_line):
                                        break
                                    # Get first word that starts with same letter
                                    words = next_line.split()
                                    if words:
                                        first_word = words[0].rstrip('.')
                                        if first_word[0].lower() == clause_title.lower():
                                            clause_title = first_word
                                            break
                                        elif first_word[0].isupper() and len(first_word) > len(clause_title):
                                            clause_title = first_word
                                            break

                    if current_clause:
                        clauses.append(current_clause)

                    current_clause = {
                        'clause_number': clause_number,
                        'title': clause_title or clause_number,
                        'text': line,
                        'page_num': current_page,
                        'span_start': char_pos,
                    }
                    title_lines_collected = 0
                    break

            # Also check for header-style clauses (all caps with colon)
            if not clause_number:
                header_match = re.match(self.clause_header_pattern, line.strip())
                if header_match:
                    clause_number = header_match.group(1).rstrip(':')
                    clause_title = clause_number

                    if current_clause:
                        clauses.append(current_clause)

                    current_clause = {
                        'clause_number': clause_number,
                        'title': clause_title,
                        'text': line,
                        'page_num': current_page,
                        'span_start': char_pos,
                    }
                    title_lines_collected = 0

            # Continue building current clause
            if current_clause:
                if line.strip():
                    current_clause['text'] += '\n' + line.strip()
                    # If we're still collecting title (first few lines), try to improve it
                    if title_lines_collected < 2 and current_clause.get('title'):
                        # Check if title is very short and we can get more from this line
                        if len(current_clause['title']) <= 3 and line.strip():
                            words = line.strip().split()
                            if words and words[0][0].isupper():
                                # Extend title with first capitalized word/phrase
                                title_words = [current_clause['title']]
                                for word in words:
                                    if '.' in word:
                                        title_words.append(word.rstrip('.'))
                                        break
                                    if word[0].isupper():
                                        title_words.append(word)
                                    else:
                                        break
                                if len(title_words) > 1:
                                    current_clause['title'] = ' '.join(title_words).strip()
                    title_lines_collected += 1
                # End clause on next numbered clause or blank section
                elif len(current_clause['text']) > 50:
                    current_clause['span_end'] = char_pos
                    clauses.append(current_clause)
                    current_clause = None
                    title_lines_collected = 0

        if current_clause:
            current_clause['span_end'] = len(text)
            clauses.append(current_clause)

        return clauses

    def _extract_metadata(self, text: str) -> Dict:
        """Extract metadata: parties, dates, governing law, terms"""
        metadata = {
            'parties': [],
            'effective_date': None,
            'governing_law': None,
            'is_mutual': None,
            'term_months': None,
            'survival_months': None,
        }

        # Extract parties
        parties = self._extract_parties(text)
        metadata['parties'] = parties

        # Determine if mutual
        mutual_keywords = ['mutual', 'both parties', 'each party', 'reciprocal']
        unilateral_keywords = ['one party', 'unilateral', 'disclosing party only']

        text_lower = text.lower()
        if any(keyword in text_lower for keyword in mutual_keywords):
            metadata['is_mutual'] = True
        elif any(keyword in text_lower for keyword in unilateral_keywords):
            metadata['is_mutual'] = False

        # Extract effective date
        effective_date = self._extract_date(text)
        if effective_date:
            metadata['effective_date'] = effective_date

        # Extract governing law
        governing_law = self._extract_governing_law(text)
        if governing_law:
            metadata['governing_law'] = governing_law

        # Extract term (duration)
        term_months = self._extract_term(text)
        if term_months:
            metadata['term_months'] = term_months

        # Extract survival period
        survival_months = self._extract_survival(text)
        if survival_months:
            metadata['survival_months'] = survival_months

        return metadata

    def _extract_parties(self, text: str) -> List[Dict]:
        """Extract party names and types"""
        parties = []

        # Try to find party definitions
        for pattern in self.party_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if match.groups():
                    for group in match.groups():
                        if group:
                            party_name = group.strip()
                            # Determine type if possible
                            party_type = None
                            if 'disclos' in match.group(0).lower():
                                party_type = 'disclosing'
                            elif 'recipient' in match.group(0).lower() or 'receiv' in match.group(0).lower():
                                party_type = 'receiving'

                            # Avoid duplicates
                            if not any(p['name'] == party_name for p in parties):
                                parties.append({
                                    'name': party_name,
                                    'type': party_type
                                })

        return parties

    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract effective date"""
        for pattern in self.date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    return date_parser.parse(date_str)
                except:
                    continue
        return None

    def _extract_governing_law(self, text: str) -> Optional[str]:
        """Extract governing law/jurisdiction"""
        for pattern in self.governing_law_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_term(self, text: str) -> Optional[int]:
        """Extract term duration in months"""
        for pattern in self.term_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = int(match.group(1))
                # Convert years to months if needed
                if 'year' in match.group(0).lower():
                    return value * 12
                return value
        return None

    def _extract_survival(self, text: str) -> Optional[int]:
        """Extract survival period in months"""
        for pattern in self.survival_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = int(match.group(1))
                # Convert years to months if needed
                if 'year' in match.group(0).lower():
                    return value * 12
                return value
        return None


# Global extractor instance
clause_extractor = ClauseExtractor()
