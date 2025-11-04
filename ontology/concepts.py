"""
Domain concepts for NDAs
"""
from typing import Dict, List


class ConfidentialityConcepts:
    """Concepts related to confidentiality"""
    CONFIDENTIAL_INFORMATION = "confidential_information"
    CONFIDENTIALITY_SCOPE = "confidentiality_scope"
    COVERED_INFORMATION = "covered_information"
    EXCLUDED_INFORMATION = "excluded_information"
    CONFIDENTIALITY_PERIOD = "confidentiality_period"
    CONFIDENTIALITY_OBLIGATION = "confidentiality_obligation"


class ExceptionConcepts:
    """Concepts related to exceptions"""
    PUBLIC_INFORMATION = "public_information"
    PUBLICLY_AVAILABLE = "publicly_available"
    INDEPENDENTLY_DEVELOPED = "independently_developed"
    LEGAL_REQUIREMENT = "legal_requirement"
    COURT_ORDER = "court_order"
    SUBPOENA = "subpoena"
    WRITTEN_CONSENT = "written_consent"
    PRIOR_APPROVAL = "prior_approval"


class TermConcepts:
    """Concepts related to temporal terms"""
    TERM = "term"
    DURATION = "duration"
    EFFECTIVE_DATE = "effective_date"
    EXPIRATION_DATE = "expiration_date"
    SURVIVAL_PERIOD = "survival_period"
    RETURN_PERIOD = "return_period"
    TERMINATION = "termination"


class ObligationConcepts:
    """Concepts related to obligations"""
    MAINTAIN_CONFIDENTIALITY = "maintain_confidentiality"
    USE_RESTRICTIONS = "use_restrictions"
    DISCLOSURE_RESTRICTIONS = "disclosure_restrictions"
    RETURN_OR_DESTROY = "return_or_destroy"
    MARK_AS_CONFIDENTIAL = "mark_as_confidential"
    NOTIFY_OF_BREACH = "notify_of_breach"


class RemedyConcepts:
    """Concepts related to remedies"""
    INJUNCTIVE_RELIEF = "injunctive_relief"
    DAMAGES = "damages"
    ATTORNEY_FEES = "attorney_fees"
    SPECIFIC_PERFORMANCE = "specific_performance"


class JurisdictionConcepts:
    """Concepts related to jurisdiction"""
    GOVERNING_LAW = "governing_law"
    JURISDICTION = "jurisdiction"
    VENUE = "venue"
    DISPUTE_RESOLUTION = "dispute_resolution"


# Concept mappings for search and categorization
CONCEPT_MAPPINGS: Dict[str, List[str]] = {
    "confidentiality": [
        ConfidentialityConcepts.CONFIDENTIAL_INFORMATION,
        ConfidentialityConcepts.CONFIDENTIALITY_SCOPE,
        ConfidentialityConcepts.COVERED_INFORMATION,
    ],
    "exceptions": [
        ExceptionConcepts.PUBLIC_INFORMATION,
        ExceptionConcepts.PUBLICLY_AVAILABLE,
        ExceptionConcepts.LEGAL_REQUIREMENT,
    ],
    "term": [
        TermConcepts.TERM,
        TermConcepts.DURATION,
        TermConcepts.EFFECTIVE_DATE,
        TermConcepts.EXPIRATION_DATE,
    ],
    "survival": [
        TermConcepts.SURVIVAL_PERIOD,
        TermConcepts.RETURN_PERIOD,
    ],
    "obligations": [
        ObligationConcepts.MAINTAIN_CONFIDENTIALITY,
        ObligationConcepts.USE_RESTRICTIONS,
        ObligationConcepts.RETURN_OR_DESTROY,
    ],
}


def get_concepts_for_category(category: str) -> List[str]:
    """Get concepts for a category"""
    return CONCEPT_MAPPINGS.get(category.lower(), [])


def get_category_for_concept(concept: str) -> str:
    """Get category for a concept"""
    for category, concepts in CONCEPT_MAPPINGS.items():
        if concept in concepts:
            return category
    return "other"
