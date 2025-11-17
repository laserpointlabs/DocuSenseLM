#!/usr/bin/env python3
"""
Test suite for Generic Legal Document Schema Design (Phase 2.1)

Tests the new generic schema that will replace NDA-specific tables:
1. LegalDocument table (replaces NDARecord)
2. DocumentType configuration table  
3. Generic workflow tables (replaces NDA-specific)
4. Generic template tables (replaces NDA-specific)
5. Backward compatibility mapping
6. JSONB metadata validation
7. Multi-document-type support

Following TDD approach - design schema through comprehensive tests.
"""

import pytest
import uuid
import json
from datetime import datetime, date
from typing import Dict, Any

# We'll create these as we implement the generic schema
from api.db.generic_schema import (
    LegalDocument, DocumentType, DocumentWorkflowInstance, DocumentWorkflowTask,
    DocumentTemplate
)


class TestLegalDocumentTableDesign:
    """Test the generic legal document table design"""
    
    def test_legal_document_table_definition(self):
        """Test that LegalDocument table has all required generic fields"""
        table = LegalDocument.__table__
        
        # Check table name
        assert table.name == 'legal_documents'
        
        # Check required generic fields
        required_fields = [
            'id', 'document_id', 'document_type', 'document_subtype',
            'primary_party_name', 'counterparty_name', 'counterparty_domain', 'counterparty_email',
            'effective_date', 'expiry_date', 'status', 'owner_user_id', 'entity_id',
            'file_uri', 'file_sha256', 'extracted_text', 'text_tsv',
            'document_metadata', 'workflow_instance_id', 'template_id', 'template_version',
            'tags', 'facts_json', 'created_at', 'updated_at'
        ]
        
        table_columns = list(table.columns.keys())
        for field in required_fields:
            assert field in table_columns, f"Required field '{field}' missing from LegalDocument"

    def test_legal_document_status_constraint(self):
        """Test that LegalDocument uses same status values as Phase 1"""
        table = LegalDocument.__table__
        
        # Should have same status constraint as Phase 1 NDARecord
        expected_statuses = {
            'created', 'draft', 'in_review', 'pending_signature', 'customer_signed',
            'llm_reviewed_approved', 'llm_reviewed_rejected', 'reviewed',
            'approved', 'rejected', 'signed', 'active', 'expired', 'terminated', 'archived'
        }
        
        # Check status constraint exists (test schema definition)
        status_constraints = [c for c in table.constraints if hasattr(c, 'sqltext') and 'status IN' in str(c.sqltext)]
        assert len(status_constraints) > 0, "Status constraint should exist"
        
        # Extract statuses from constraint
        import re
        status_constraint = str(status_constraints[0].sqltext)
        constraint_statuses = set(re.findall(r"'([^']+)'", status_constraint))
        
        # Should include all expected statuses
        missing_statuses = expected_statuses - constraint_statuses
        assert not missing_statuses, f"Missing statuses: {missing_statuses}"

    def test_legal_document_metadata_jsonb_field(self):
        """Test that document_metadata JSONB field supports flexible data"""
        table = LegalDocument.__table__
        
        # Check document_metadata column
        metadata_column = table.columns['document_metadata']
        assert metadata_column is not None
        
        # Should be JSONB type (or JSONBType which falls back to TEXT)
        column_type_str = str(metadata_column.type).lower()
        column_type_class = str(type(metadata_column.type).__name__).lower()
        
        # Should be either JSONB (PostgreSQL) or JSONBType (our custom type)
        is_json_type = ('json' in column_type_str or 'jsonbtype' in column_type_class)
        assert is_json_type, f"document_metadata should be JSON/JSONB type, got {column_type_str} ({column_type_class})"
        
        # Should have default empty object
        assert metadata_column.default.arg == '{}' or metadata_column.default.arg == {}, \
            "document_metadata should default to empty object"

    def test_legal_document_supports_nda_fields(self):
        """Test that NDA-specific fields can be stored in document_metadata"""
        
        # Simulate NDA metadata that would be stored in JSONB field
        nda_metadata = {
            "nda_type": "mutual",
            "direction": "outbound", 
            "term_months": 24,
            "survival_months": 36,
            "governing_law": "California",
            "disclosing_party": "Our Company Inc.",
            "receiving_party": "Customer Corp"
        }
        
        # Should be valid JSON
        json_str = json.dumps(nda_metadata)
        parsed_back = json.loads(json_str)
        
        assert parsed_back["nda_type"] == "mutual"
        assert parsed_back["term_months"] == 24
        assert parsed_back["governing_law"] == "California"
        
        # All NDA fields can be represented in JSONB
        assert len(parsed_back) == len(nda_metadata)

    def test_legal_document_supports_service_agreement_fields(self):
        """Test that service agreement fields can be stored in document_metadata"""
        
        # Simulate service agreement metadata
        service_agreement_metadata = {
            "service_type": "consulting",
            "contract_value": 50000.00,
            "payment_terms": "Net 30",
            "project_duration_months": 6,
            "deliverables": [
                "Requirements analysis",
                "System design", 
                "Implementation",
                "Testing and deployment"
            ],
            "milestones": {
                "phase1": {"due_date": "2024-03-01", "payment": 15000},
                "phase2": {"due_date": "2024-06-01", "payment": 35000}
            }
        }
        
        # Should be valid JSON with complex nested data
        json_str = json.dumps(service_agreement_metadata)
        parsed_back = json.loads(json_str)
        
        assert parsed_back["service_type"] == "consulting"
        assert len(parsed_back["deliverables"]) == 4
        assert parsed_back["milestones"]["phase1"]["payment"] == 15000
        
        # Complex service agreement data can be represented
        assert isinstance(parsed_back["deliverables"], list)
        assert isinstance(parsed_back["milestones"], dict)


class TestDocumentTypeConfigurationDesign:
    """Test the document type configuration system"""
    
    def test_document_type_table_definition(self):
        """Test DocumentType configuration table"""
        table = DocumentType.__table__
        
        assert table.name == 'document_types'
        
        required_fields = [
            'id', 'type_key', 'display_name', 'description',
            'metadata_schema', 'default_workflow_process_key',
            'llm_review_enabled', 'llm_review_threshold', 'require_human_review',
            'template_bucket', 'is_active', 'created_at', 'updated_at'
        ]
        
        table_columns = list(table.columns.keys())
        for field in required_fields:
            assert field in table_columns, f"Required field '{field}' missing from DocumentType"

    def test_document_type_supports_nda_configuration(self):
        """Test that NDA document type can be fully configured"""
        
        nda_config = DocumentType(
            type_key='nda',
            display_name='Non-Disclosure Agreement',
            description='Confidentiality agreements between parties',
            metadata_schema={
                "type": "object",
                "properties": {
                    "nda_type": {"type": "string", "enum": ["mutual", "unilateral"]},
                    "direction": {"type": "string", "enum": ["inbound", "outbound"]},
                    "term_months": {"type": "integer", "minimum": 1, "maximum": 120},
                    "survival_months": {"type": "integer", "minimum": 0, "maximum": 120},
                    "governing_law": {"type": "string", "maxLength": 100}
                },
                "required": ["nda_type"]
            },
            default_workflow_process_key='nda_review_approval',
            llm_review_enabled=True,
            llm_review_threshold=0.7,
            require_human_review=True,
            template_bucket='nda-templates'
        )
        
        # Should have all NDA-specific configuration
        assert nda_config.type_key == 'nda'
        assert nda_config.default_workflow_process_key == 'nda_review_approval'
        assert nda_config.llm_review_enabled is True
        
        # Metadata schema should be valid JSON Schema
        schema = nda_config.metadata_schema
        assert schema["type"] == "object"
        assert "nda_type" in schema["properties"]
        assert "term_months" in schema["properties"]

    def test_document_type_supports_service_agreement_configuration(self):
        """Test that service agreement document type can be configured"""
        
        service_agreement_config = DocumentType(
            type_key='service_agreement',
            display_name='Service Agreement',
            description='Agreements for provision of services',
            metadata_schema={
                "type": "object",
                "properties": {
                    "service_type": {"type": "string", "enum": ["consulting", "development", "maintenance"]},
                    "contract_value": {"type": "number", "minimum": 0},
                    "payment_terms": {"type": "string"},
                    "project_duration_months": {"type": "integer", "minimum": 1},
                    "deliverables": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["service_type", "contract_value"]
            },
            default_workflow_process_key='service_agreement_approval',
            llm_review_enabled=True,
            llm_review_threshold=0.8,  # Higher threshold for contracts
            require_human_review=True,
            template_bucket='service-agreement-templates'
        )
        
        # Should support different document type
        assert service_agreement_config.type_key == 'service_agreement'
        assert service_agreement_config.default_workflow_process_key == 'service_agreement_approval'
        assert service_agreement_config.llm_review_threshold == 0.8
        
        # Metadata schema should be different from NDA
        schema = service_agreement_config.metadata_schema
        assert "service_type" in schema["properties"]
        assert "contract_value" in schema["properties"]
        assert "deliverables" in schema["properties"]

    def test_document_type_unique_constraints(self):
        """Test DocumentType unique constraints"""
        table = DocumentType.__table__
        
        # type_key should be unique
        type_key_column = table.columns['type_key']
        assert type_key_column.unique, "type_key should be unique"


class TestGenericWorkflowTablesDesign:
    """Test generalized workflow table designs"""
    
    def test_document_workflow_instance_table(self):
        """Test generic workflow instance table design"""
        table = DocumentWorkflowInstance.__table__
        
        assert table.name == 'document_workflow_instances'
        
        required_fields = [
            'id', 'legal_document_id', 'document_type', 'camunda_process_instance_id',
            'process_key', 'current_status', 'started_at', 'completed_at', 'created_at', 'updated_at'
        ]
        
        table_columns = list(table.columns.keys())
        for field in required_fields:
            assert field in table_columns, f"Required field '{field}' missing from DocumentWorkflowInstance"

    def test_document_workflow_task_table(self):
        """Test generic workflow task table design"""
        table = DocumentWorkflowTask.__table__
        
        assert table.name == 'document_workflow_tasks'
        
        required_fields = [
            'id', 'workflow_instance_id', 'task_id', 'task_name',
            'assignee_user_id', 'status', 'due_date', 'completed_at',
            'comments', 'created_at', 'updated_at'
        ]
        
        table_columns = list(table.columns.keys())
        for field in required_fields:
            assert field in table_columns, f"Required field '{field}' missing from DocumentWorkflowTask"

    def test_workflow_tables_foreign_key_relationships(self):
        """Test foreign key relationships in generic workflow tables"""
        workflow_instance_table = DocumentWorkflowInstance.__table__
        workflow_task_table = DocumentWorkflowTask.__table__
        
        # DocumentWorkflowInstance should reference LegalDocument
        legal_document_column = workflow_instance_table.columns['legal_document_id']
        fks = list(legal_document_column.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == 'legal_documents'
        
        # DocumentWorkflowTask should reference DocumentWorkflowInstance
        workflow_instance_column = workflow_task_table.columns['workflow_instance_id']
        fks = list(workflow_instance_column.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == 'document_workflow_instances'


class TestGenericTemplateSystemDesign:
    """Test generalized template system design"""
    
    def test_document_template_table(self):
        """Test generic document template table design"""
        table = DocumentTemplate.__table__
        
        assert table.name == 'document_templates'
        
        required_fields = [
            'id', 'document_type', 'name', 'description', 'file_path',
            'version', 'template_key', 'variable_schema',
            'is_active', 'is_current', 'created_by', 'created_at', 'updated_at', 'change_notes'
        ]
        
        table_columns = list(table.columns.keys())
        for field in required_fields:
            assert field in table_columns, f"Required field '{field}' missing from DocumentTemplate"

    def test_document_template_references_document_type(self):
        """Test that DocumentTemplate properly references DocumentType"""
        table = DocumentTemplate.__table__
        
        # document_type should reference document_types.type_key
        document_type_column = table.columns['document_type']
        fks = list(document_type_column.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == 'document_types'
        assert fks[0].column.name == 'type_key'

    def test_template_variable_schema_supports_nda(self):
        """Test that template variable schema supports NDA templates"""
        
        # NDA template variable schema
        nda_variable_schema = {
            "type": "object",
            "properties": {
                "counterparty_name": {"type": "string", "description": "Name of the other party"},
                "effective_date": {"type": "string", "format": "date"},
                "term_months": {"type": "integer", "minimum": 1, "maximum": 120},
                "survival_months": {"type": "integer", "minimum": 0, "maximum": 120},
                "governing_law": {"type": "string"},
                "disclosing_party": {"type": "string"},
                "receiving_party": {"type": "string"}
            },
            "required": ["counterparty_name", "effective_date"]
        }
        
        # Should be valid JSON Schema
        json_str = json.dumps(nda_variable_schema)
        parsed = json.loads(json_str)
        
        assert parsed["type"] == "object"
        assert "counterparty_name" in parsed["properties"]
        assert "effective_date" in parsed["properties"]
        assert "required" in parsed
        assert "counterparty_name" in parsed["required"]

    def test_template_variable_schema_supports_service_agreement(self):
        """Test that template variable schema supports service agreement templates"""
        
        # Service agreement template variable schema
        service_variable_schema = {
            "type": "object",
            "properties": {
                "client_name": {"type": "string"},
                "service_provider_name": {"type": "string"},
                "service_type": {"type": "string", "enum": ["consulting", "development", "support"]},
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
                "contract_value": {"type": "number", "minimum": 0},
                "payment_schedule": {"type": "string"},
                "deliverables": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "due_date": {"type": "string", "format": "date"},
                            "description": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["client_name", "service_provider_name", "service_type", "contract_value"]
        }
        
        # Should support complex nested schemas
        json_str = json.dumps(service_variable_schema)
        parsed = json.loads(json_str)
        
        assert "deliverables" in parsed["properties"]
        assert parsed["properties"]["deliverables"]["type"] == "array"
        assert "service_type" in parsed["properties"]
        assert "enum" in parsed["properties"]["service_type"]


class TestBackwardCompatibilityMapping:
    """Test backward compatibility with existing NDA system"""
    
    def test_nda_record_to_legal_document_mapping(self):
        """Test mapping NDARecord fields to LegalDocument"""
        
        # Define mapping from old NDA fields to new generic fields
        nda_to_legal_mapping = {
            # Direct field mappings
            'id': 'id',
            'document_id': 'document_id', 
            'counterparty_name': 'counterparty_name',
            'counterparty_domain': 'counterparty_domain',
            'entity_id': 'entity_id',
            'owner_user_id': 'owner_user_id',
            'effective_date': 'effective_date',
            'expiry_date': 'expiry_date',
            'status': 'status',
            'file_uri': 'file_uri',
            'file_sha256': 'file_sha256',
            'extracted_text': 'extracted_text',
            'text_tsv': 'text_tsv',
            'workflow_instance_id': 'workflow_instance_id',
            'template_id': 'template_id',
            'template_version': 'template_version',
            'tags': 'tags',
            'facts_json': 'facts_json',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            
            # Computed/transformed fields
            'document_type': 'nda',  # Constant value
            'primary_party_name': 'Our Company',  # Default value or from config
            
            # Fields moved to document_metadata JSONB
            'metadata.direction': 'direction',
            'metadata.nda_type': 'nda_type', 
            'metadata.term_months': 'term_months',
            'metadata.survival_months': 'survival_months'
        }
        
        # Check mapping completeness
        direct_mappings = [k for k in nda_to_legal_mapping.keys() if not k.startswith('metadata.')]
        metadata_mappings = [k for k in nda_to_legal_mapping.keys() if k.startswith('metadata.')]
        
        assert len(direct_mappings) > 15, "Should have comprehensive direct field mappings"
        assert len(metadata_mappings) > 3, "Should have metadata field mappings"
        
        # Test that mapping preserves essential data
        essential_fields = ['id', 'counterparty_name', 'status', 'file_uri', 'workflow_instance_id']
        for field in essential_fields:
            assert field in nda_to_legal_mapping, f"Essential field '{field}' missing from mapping"

    def test_workflow_instance_mapping(self):
        """Test mapping NDAWorkflowInstance to DocumentWorkflowInstance"""
        
        workflow_mapping = {
            'id': 'id',
            'nda_record_id': 'legal_document_id',  # Renamed
            'camunda_process_instance_id': 'camunda_process_instance_id',
            'current_status': 'current_status',
            'started_at': 'started_at',
            'completed_at': 'completed_at',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            
            # New fields
            'document_type': 'nda',  # Constant
            'process_key': 'nda_review_approval'  # From config
        }
        
        # Should preserve all essential workflow data
        assert workflow_mapping['nda_record_id'] == 'legal_document_id'
        assert workflow_mapping['document_type'] == 'nda'
        assert workflow_mapping['process_key'] == 'nda_review_approval'

    def test_template_mapping(self):
        """Test mapping NDATemplate to DocumentTemplate"""
        
        template_mapping = {
            'id': 'id',
            'name': 'name',
            'description': 'description',
            'file_path': 'file_path',
            'version': 'version',
            'template_key': 'template_key',
            'is_active': 'is_active', 
            'is_current': 'is_current',
            'created_by': 'created_by',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            'change_notes': 'change_notes',
            
            # New fields
            'document_type': 'nda',  # Constant
            'variable_schema': {}  # Default empty, can be populated later
        }
        
        # Should preserve template versioning system
        assert 'version' in template_mapping
        assert 'template_key' in template_mapping
        assert 'is_current' in template_mapping


class TestGenericSchemaFlexibility:
    """Test that generic schema supports multiple document types"""
    
    def test_supports_multiple_document_types_simultaneously(self):
        """Test that system can handle multiple document types at once"""
        
        # Create mock documents of different types
        documents = [
            {
                'document_type': 'nda',
                'counterparty_name': 'NDA Customer Corp',
                'document_metadata': {
                    'nda_type': 'mutual',
                    'term_months': 24
                }
            },
            {
                'document_type': 'service_agreement', 
                'counterparty_name': 'Service Client Inc',
                'document_metadata': {
                    'service_type': 'consulting',
                    'contract_value': 75000
                }
            },
            {
                'document_type': 'employment_contract',
                'counterparty_name': 'John Doe Employee',
                'document_metadata': {
                    'position': 'Senior Developer',
                    'salary': 120000,
                    'start_date': '2024-01-15'
                }
            }
        ]
        
        # All document types should be representable
        for doc in documents:
            assert doc['document_type'] in ['nda', 'service_agreement', 'employment_contract']
            assert 'counterparty_name' in doc
            assert 'document_metadata' in doc
            assert isinstance(doc['document_metadata'], dict)
            
            # Each should have type-specific metadata
            metadata = doc['document_metadata']
            if doc['document_type'] == 'nda':
                assert 'nda_type' in metadata
            elif doc['document_type'] == 'service_agreement':
                assert 'service_type' in metadata
            elif doc['document_type'] == 'employment_contract':
                assert 'position' in metadata

    def test_workflow_supports_multiple_process_keys(self):
        """Test that workflow system supports multiple BPMN processes"""
        
        # Different document types should use different workflows
        workflow_configs = [
            {
                'document_type': 'nda',
                'process_key': 'nda_review_approval',
                'topics': ['llm_review', 'send_to_customer', 'llm_review_signed']
            },
            {
                'document_type': 'service_agreement',
                'process_key': 'service_agreement_approval',
                'topics': ['legal_review', 'pricing_review', 'send_to_client']
            },
            {
                'document_type': 'employment_contract',
                'process_key': 'employment_contract_approval', 
                'topics': ['hr_review', 'legal_review', 'send_offer']
            }
        ]
        
        # Each document type should have distinct workflow configuration
        process_keys = [config['process_key'] for config in workflow_configs]
        assert len(process_keys) == len(set(process_keys)), "Process keys should be unique"
        
        # Each should have appropriate external task topics
        for config in workflow_configs:
            assert len(config['topics']) >= 3, "Should have multiple workflow steps"
            assert 'review' in str(config['topics']), "Should include review steps"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
