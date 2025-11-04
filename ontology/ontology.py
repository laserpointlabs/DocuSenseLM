"""
Core ontology definitions for NDA domain
"""
from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum


class PartyType(Enum):
    """Party types in an NDA"""
    DISCLOSING = "disclosing"
    RECEIVING = "receiving"
    BOTH = "both"  # For mutual NDAs


class ClauseType(Enum):
    """Clause types"""
    TITLE = "title"
    RECITAL = "recital"
    CONFIDENTIALITY = "confidentiality"
    EXCEPTION = "exception"
    OBLIGATION = "obligation"
    TERM = "term"
    SURVIVAL = "survival"
    RETURN = "return"
    REMEDY = "remedy"
    JURISDICTION = "jurisdiction"
    SIGNATURE = "signature"


@dataclass
class Party:
    """Represents a party in an NDA"""
    name: str
    party_type: PartyType
    address: Optional[str] = None


@dataclass
class Clause:
    """Represents a clause in an NDA"""
    clause_number: str
    clause_type: ClauseType
    text: str
    page_num: int
    span_start: int
    span_end: int


@dataclass
class Obligation:
    """Represents an obligation or restriction"""
    description: str
    applies_to: PartyType
    clause_reference: str


@dataclass
class Exception:
    """Represents an exception to confidentiality"""
    description: str
    clause_reference: str


@dataclass
class Term:
    """Represents a temporal term"""
    name: str
    duration_months: Optional[int] = None
    duration_years: Optional[int] = None
    clause_reference: str = ""


@dataclass
class Document:
    """Represents an NDA document"""
    document_id: str
    title: str
    parties: List[Party]
    clauses: List[Clause]
    obligations: List[Obligation]
    exceptions: List[Exception]
    terms: List[Term]
    governing_law: Optional[str] = None
    effective_date: Optional[str] = None
    is_mutual: Optional[bool] = None


class NDACoreConcepts:
    """Core concepts in NDA domain"""

    CONFIDENTIALITY = "confidentiality"
    CONFIDENTIAL_INFORMATION = "confidential_information"
    DISCLOSURE = "disclosure"
    OBLIGATION = "obligation"
    EXCEPTION = "exception"
    TERM = "term"
    SURVIVAL = "survival"
    RETURN = "return"
    DESTRUCTION = "destruction"
    REMEDY = "remedy"
    BREACH = "breach"
    JURISDICTION = "jurisdiction"
    GOVERNING_LAW = "governing_law"


class NDAConceptHierarchy:
    """Hierarchical organization of NDA concepts"""

    ROOT = "nda"

    STRUCTURE = {
        "nda": {
            "parties": ["disclosing_party", "receiving_party"],
            "clauses": [
                "confidentiality",
                "exceptions",
                "obligations",
                "term",
                "survival",
                "return",
                "remedies",
                "jurisdiction"
            ],
            "metadata": [
                "effective_date",
                "expiration_date",
                "governing_law",
                "mutual_status"
            ]
        },
        "confidentiality": {
            "scope": ["definition", "covered_information", "exclusions"],
            "duration": ["term", "survival_period"],
            "restrictions": ["disclosure", "use", "copying"]
        },
        "exceptions": {
            "public_information": ["publicly_available", "independently_developed"],
            "legal_requirements": ["court_order", "subpoena"],
            "consent": ["written_consent", "prior_approval"]
        },
        "obligations": {
            "receiving_party": ["maintain_confidentiality", "use_restrictions", "return_or_destroy"],
            "disclosing_party": ["mark_as_confidential", "identify_in_writing"]
        },
        "term": {
            "duration": ["months", "years", "indefinite"],
            "start_date": ["effective_date", "execution_date"],
            "end_date": ["expiration_date", "termination_date"]
        }
    }


def get_concept_path(concept: str) -> Optional[List[str]]:
    """Get the path to a concept in the hierarchy"""
    def search_in_dict(d: Dict, target: str, path: List[str] = []) -> Optional[List[str]]:
        for key, value in d.items():
            current_path = path + [key]
            if key == target:
                return current_path
            if isinstance(value, dict):
                result = search_in_dict(value, target, current_path)
                if result:
                    return result
            elif isinstance(value, list) and target in value:
                return current_path + [target]
        return None

    return search_in_dict(NDAConceptHierarchy.STRUCTURE, concept)


def get_related_concepts(concept: str) -> List[str]:
    """Get related concepts for a given concept"""
    path = get_concept_path(concept)
    if not path:
        return []

    # Get sibling concepts
    if len(path) >= 2:
        parent = path[-2]
        if parent in NDAConceptHierarchy.STRUCTURE:
            parent_dict = NDAConceptHierarchy.STRUCTURE[parent]
            if isinstance(parent_dict, dict):
                siblings = []
                for key, value in parent_dict.items():
                    if key != path[-1]:
                        if isinstance(value, list):
                            siblings.extend(value)
                        else:
                            siblings.append(key)
                return siblings

    return []
