"""
Ontology service for NDA domain queries
"""
from typing import List, Dict, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ontology.ontology import (
    NDACoreConcepts, NDAConceptHierarchy,
    get_concept_path, get_related_concepts
)
from ontology.concepts import (
    get_concepts_for_category, get_category_for_concept
)


class OntologyService:
    """Service for ontology queries and entity extraction"""

    def get_concept_hierarchy(self) -> Dict:
        """Get the full concept hierarchy"""
        return NDAConceptHierarchy.STRUCTURE

    def get_concepts_for_category(self, category: str) -> List[str]:
        """Get concepts for a category"""
        return get_concepts_for_category(category)

    def get_category_for_concept(self, concept: str) -> str:
        """Get category for a concept"""
        return get_category_for_concept(concept)

    def get_concept_path(self, concept: str) -> Optional[List[str]]:
        """Get path to a concept in the hierarchy"""
        return get_concept_path(concept)

    def get_related_concepts(self, concept: str) -> List[str]:
        """Get related concepts"""
        return get_related_concepts(concept)

    def suggest_question_categories(self, question_text: str) -> List[str]:
        """Suggest question categories based on question text"""
        question_lower = question_text.lower()
        categories = []

        # Check for category keywords
        category_keywords = {
            "confidentiality": ["confidential", "confidentiality", "information", "scope"],
            "exceptions": ["exception", "excluded", "not confidential", "carve-out"],
            "term": ["term", "duration", "period", "months", "years"],
            "survival": ["survival", "after", "expiration", "continue"],
            "obligations": ["obligation", "must", "shall", "duty", "restriction"],
            "remedies": ["remedy", "breach", "damages", "injunction", "relief"],
            "jurisdiction": ["governing law", "jurisdiction", "venue", "law"],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                categories.append(category)

        return categories if categories else ["general"]


# Global service instance
ontology_service = OntologyService()
