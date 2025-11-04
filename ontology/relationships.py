"""
Relationship definitions between NDA entities
"""
from dataclasses import dataclass
from typing import Optional
from .entities import Entity


@dataclass
class Relationship:
    """Base relationship class"""
    relationship_type: str
    source_entity_id: str
    target_entity_id: str
    metadata: Optional[dict] = None


class RelationshipTypes:
    """Standard relationship types"""
    PARTY_HAS_ROLE = "party_has_role"
    CLAUSE_CONTAINS_OBLIGATION = "clause_contains_obligation"
    CLAUSE_HAS_TERM = "clause_has_term"
    CLAUSE_REFERENCES_TERM = "clause_references_term"
    DOCUMENT_GOVERNED_BY_LAW = "document_governed_by_law"
    PARTY_APPEARS_IN_DOCUMENT = "party_appears_in_document"
    CLAUSE_IN_DOCUMENT = "clause_in_document"
    EXCEPTION_APPLIES_TO = "exception_applies_to"
    OBLIGATION_APPLIES_TO = "obligation_applies_to"


@dataclass
class PartyHasRole(Relationship):
    """Party has a role in a document"""
    role: str  # "disclosing", "receiving", "both"

    def __post_init__(self):
        self.relationship_type = RelationshipTypes.PARTY_HAS_ROLE


@dataclass
class ClauseContainsObligation(Relationship):
    """Clause contains an obligation"""
    def __post_init__(self):
        self.relationship_type = RelationshipTypes.CLAUSE_CONTAINS_OBLIGATION


@dataclass
class ClauseHasTerm(Relationship):
    """Clause defines a term"""
    term_type: str  # "duration", "survival", "return_period"

    def __post_init__(self):
        self.relationship_type = RelationshipTypes.CLAUSE_HAS_TERM


@dataclass
class DocumentGovernedByLaw(Relationship):
    """Document is governed by a law/jurisdiction"""
    jurisdiction: str

    def __post_init__(self):
        self.relationship_type = RelationshipTypes.DOCUMENT_GOVERNED_BY_LAW
        if self.metadata is None:
            self.metadata = {}
        self.metadata['jurisdiction'] = self.jurisdiction


def extract_relationships_from_document(document_data: dict) -> list:
    """
    Extract relationships from parsed document data

    Args:
        document_data: Dictionary with document structure from clause extractor

    Returns:
        List of Relationship objects
    """
    relationships = []
    document_id = document_data.get('document_id', '')

    # Party-document relationships
    for party in document_data.get('parties', []):
        rel = PartyHasRole(
            source_entity_id=party.get('name', ''),
            target_entity_id=document_id,
            role=party.get('type', 'unknown')
        )
        relationships.append(rel)

    # Clause-document relationships
    for clause in document_data.get('clauses', []):
        rel = Relationship(
            relationship_type=RelationshipTypes.CLAUSE_IN_DOCUMENT,
            source_entity_id=clause.get('clause_number', ''),
            target_entity_id=document_id
        )
        relationships.append(rel)

    # Governing law relationship
    if document_data.get('metadata', {}).get('governing_law'):
        rel = DocumentGovernedByLaw(
            source_entity_id=document_id,
            target_entity_id=document_data['metadata']['governing_law'],
            jurisdiction=document_data['metadata']['governing_law']
        )
        relationships.append(rel)

    return relationships
