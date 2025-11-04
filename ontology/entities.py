"""
NDA entity definitions
"""
from dataclasses import dataclass
from typing import List, Optional
from .ontology import PartyType, ClauseType


@dataclass
class Entity:
    """Base entity class"""
    entity_id: str
    name: str
    entity_type: str


@dataclass
class PartyEntity(Entity):
    """Party entity"""
    party_type: PartyType
    address: Optional[str] = None
    documents: List[str] = None  # Document IDs this party appears in

    def __post_init__(self):
        if self.documents is None:
            self.documents = []
        self.entity_type = "party"


@dataclass
class ClauseEntity(Entity):
    """Clause entity"""
    clause_type: ClauseType
    clause_number: str
    document_id: str
    page_num: int
    span_start: int
    span_end: int
    text: str

    def __post_init__(self):
        self.entity_type = "clause"


@dataclass
class TermEntity(Entity):
    """Term entity (temporal terms like duration, survival)"""
    duration_months: Optional[int] = None
    duration_years: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    clause_reference: str = ""

    def __post_init__(self):
        self.entity_type = "term"


@dataclass
class JurisdictionEntity(Entity):
    """Jurisdiction entity"""
    jurisdiction_type: str = "governing_law"  # or "jurisdiction", "venue"
    clause_reference: str = ""

    def __post_init__(self):
        self.entity_type = "jurisdiction"


@dataclass
class ObligationEntity(Entity):
    """Obligation entity"""
    applies_to: PartyType
    obligation_type: str  # e.g., "maintain_confidentiality", "return_or_destroy"
    clause_reference: str = ""

    def __post_init__(self):
        self.entity_type = "obligation"


@dataclass
class ExceptionEntity(Entity):
    """Exception entity"""
    exception_type: str  # e.g., "public_information", "legal_requirement"
    clause_reference: str = ""

    def __post_init__(self):
        self.entity_type = "exception"
