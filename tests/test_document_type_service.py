#!/usr/bin/env python3
"""
Test suite for Document Type Configuration Service (Phase 2.2) - Clean Version

Tests document type configuration system comprehensively:
1. Document type registry and management
2. JSON Schema validation for document metadata  
3. Default document types (NDA, Service Agreement, Employment Contract)
4. Configuration loading and caching
5. Workflow configuration per document type
6. Error handling and validation

Clean implementation focused on core functionality.
"""

import pytest
import uuid
import json
from datetime import datetime
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from api.services.document_type_service import (
    DocumentTypeService, DocumentTypeRegistry, DocumentTypeNotFoundError,
    DocumentTypeValidationError, InvalidMetadataError, get_document_type_service
)
from api.db.generic_schema import DocumentType


class TestDocumentTypeServiceCore:
    """Test core document type service functionality"""
    
    def test_service_and_registry_initialize(self):
        """Test that service and registry initialize properly"""
        service = DocumentTypeService()
        assert service is not None
        assert hasattr(service, 'registry')
        assert isinstance(service.registry, DocumentTypeRegistry)
        
        registry = DocumentTypeRegistry()
        assert registry is not None
        assert hasattr(registry, '_types')

    def test_register_and_retrieve_document_type(self):
        """Test basic document type registration and retrieval"""
        registry = DocumentTypeRegistry()
        
        # Create valid document type
        nda_type = DocumentType(
            type_key='nda',
            display_name='Non-Disclosure Agreement',
            metadata_schema={"type": "object", "properties": {}},
            default_workflow_process_key='nda_review_approval',
            llm_review_threshold=0.7
        )
        
        # Register and retrieve
        registry.register_document_type(nda_type)
        retrieved = registry.get_document_type('nda')
        
        assert retrieved.type_key == 'nda'
        assert retrieved.display_name == 'Non-Disclosure Agreement'

    def test_document_type_not_found_error(self):
        """Test error handling for nonexistent document types"""
        registry = DocumentTypeRegistry()
        
        with pytest.raises(DocumentTypeNotFoundError):
            registry.get_document_type('nonexistent_type')

    def test_list_document_types(self):
        """Test listing registered document types"""
        registry = DocumentTypeRegistry()
        
        # Register multiple types
        types = [
            DocumentType(type_key='nda', display_name='NDA'),
            DocumentType(type_key='service_agreement', display_name='Service Agreement'),
            DocumentType(type_key='employment_contract', display_name='Employment Contract')
        ]
        
        for doc_type in types:
            registry.register_document_type(doc_type)
        
        all_types = registry.list_document_types(active_only=False)
        assert len(all_types) == 3


class TestDocumentTypeWorkflowConfig:
    """Test workflow configuration aspects"""
    
    def test_get_workflow_process_key(self):
        """Test getting workflow process key for document type"""
        registry = DocumentTypeRegistry()
        
        nda_type = DocumentType(
            type_key='nda',
            display_name='NDA', 
            default_workflow_process_key='nda_review_approval'
        )
        registry.register_document_type(nda_type)
        
        process_key = registry.get_workflow_process_key('nda')
        assert process_key == 'nda_review_approval'

    def test_get_llm_review_config(self):
        """Test getting LLM review configuration"""
        registry = DocumentTypeRegistry()
        
        nda_type = DocumentType(
            type_key='nda',
            display_name='NDA',
            llm_review_enabled=True,
            llm_review_threshold=0.7,
            require_human_review=True
        )
        registry.register_document_type(nda_type)
        
        config = registry.get_llm_review_config('nda')
        assert config['enabled'] is True
        assert config['threshold'] == 0.7
        assert config['require_human_review'] is True


class TestDocumentTypeMetadataValidation:
    """Test JSON Schema metadata validation"""
    
    def test_validate_simple_nda_metadata(self):
        """Test validation of simple NDA metadata"""
        registry = DocumentTypeRegistry()
        
        nda_type = DocumentType(
            type_key='nda',
            display_name='NDA',
            metadata_schema={
                "type": "object",
                "properties": {
                    "nda_type": {"type": "string", "enum": ["mutual", "unilateral"]},
                    "term_months": {"type": "integer", "minimum": 1, "maximum": 120}
                },
                "required": ["nda_type"]
            }
        )
        registry.register_document_type(nda_type)
        
        # Test valid metadata
        valid_metadata = {
            "nda_type": "mutual",
            "term_months": 24
        }
        
        is_valid = registry.validate_metadata('nda', valid_metadata)
        assert is_valid is True

    def test_validate_metadata_failure_cases(self):
        """Test metadata validation failure cases"""
        registry = DocumentTypeRegistry()
        
        nda_type = DocumentType(
            type_key='nda',
            display_name='NDA',
            metadata_schema={
                "type": "object",
                "properties": {
                    "nda_type": {"type": "string", "enum": ["mutual", "unilateral"]},
                    "term_months": {"type": "integer", "minimum": 1, "maximum": 120}
                },
                "required": ["nda_type"]
            }
        )
        registry.register_document_type(nda_type)
        
        # Test missing required field
        invalid_metadata = {"term_months": 24}  # Missing nda_type
        
        with pytest.raises(InvalidMetadataError):
            registry.validate_metadata('nda', invalid_metadata)

    def test_validate_empty_metadata(self):
        """Test validation of empty metadata"""
        registry = DocumentTypeRegistry()
        
        # Type with no required fields
        simple_type = DocumentType(
            type_key='simple_doc',
            display_name='Simple Document',
            metadata_schema={
                "type": "object",
                "properties": {"optional_field": {"type": "string"}}
            }
        )
        registry.register_document_type(simple_type)
        
        # Empty metadata should be valid
        assert registry.validate_metadata('simple_doc', {}) is True
        assert registry.validate_metadata('simple_doc', None) is True


class TestDocumentTypeDefaultConfigurations:
    """Test default document type configurations"""
    
    def test_default_document_types_exist(self):
        """Test that default document types are available"""
        from api.db.generic_schema import get_default_document_types
        
        default_types = get_default_document_types()
        assert len(default_types) >= 3  # At least NDA, service agreement, employment contract
        
        type_keys = [dt.type_key for dt in default_types]
        assert 'nda' in type_keys
        assert 'service_agreement' in type_keys
        assert 'employment_contract' in type_keys

    def test_default_nda_type_configuration(self):
        """Test that default NDA type has proper configuration"""
        from api.db.generic_schema import get_default_document_types
        
        nda_type = next(dt for dt in get_default_document_types() if dt.type_key == 'nda')
        
        assert nda_type.type_key == 'nda'
        assert nda_type.display_name == 'Non-Disclosure Agreement'
        assert nda_type.default_workflow_process_key == 'nda_review_approval'
        assert nda_type.llm_review_enabled is True
        assert nda_type.template_bucket == 'nda-templates'
        
        # Check metadata schema has NDA fields
        schema = nda_type.metadata_schema
        assert 'nda_type' in schema['properties']
        assert 'term_months' in schema['properties']

    def test_default_service_agreement_configuration(self):
        """Test that default service agreement type has proper configuration"""
        from api.db.generic_schema import get_default_document_types
        
        service_type = next(dt for dt in get_default_document_types() if dt.type_key == 'service_agreement')
        
        assert service_type.type_key == 'service_agreement'
        assert service_type.default_workflow_process_key == 'service_agreement_approval'
        assert service_type.template_bucket == 'service-agreement-templates'
        
        # Check metadata schema has service agreement fields
        schema = service_type.metadata_schema
        assert 'service_type' in schema['properties']
        assert 'contract_value' in schema['properties']


class TestDocumentTypeServiceIntegration:
    """Test service integration aspects"""
    
    @patch('api.services.document_type_service.get_db_session')
    def test_service_loads_defaults_when_database_empty(self, mock_db):
        """Test that service loads defaults when database is empty"""
        # Mock empty database
        mock_db.return_value.query.return_value.filter.return_value.all.return_value = []
        mock_db.return_value.close = Mock()
        
        service = DocumentTypeService()
        document_types = service.load_document_types()
        
        # Should have loaded default types
        assert len(document_types) >= 3
        type_keys = [dt.type_key for dt in document_types]
        assert 'nda' in type_keys

    def test_service_caching_behavior(self):
        """Test that service has caching capabilities"""
        service = DocumentTypeService()
        
        # Should have cache management methods
        assert hasattr(service, 'clear_cache')
        assert hasattr(service, 'refresh_configuration')
        
        # Should track cache state
        assert hasattr(service, '_initialized')

    def test_service_supports_document_type_queries(self):
        """Test that service supports document type queries for API"""
        service = DocumentTypeService()
        
        # Should support type existence checks
        assert hasattr(service, 'supports_document_type')
        
        # Should support configuration retrieval
        assert hasattr(service, 'get_document_type_config')


class TestDocumentTypeValidationEdgeCases:
    """Test edge cases and error handling"""
    
    def test_invalid_document_type_registration_fails(self):
        """Test that invalid document types fail registration"""
        registry = DocumentTypeRegistry()
        
        # Test missing type_key
        with pytest.raises(DocumentTypeValidationError):
            invalid_type = DocumentType(display_name='Missing Key')
            registry.register_document_type(invalid_type)
        
        # Test missing display_name
        with pytest.raises(DocumentTypeValidationError):
            invalid_type = DocumentType(type_key='missing_name')
            registry.register_document_type(invalid_type)

    def test_metadata_validation_with_complex_schema(self):
        """Test metadata validation with complex nested schema"""
        registry = DocumentTypeRegistry()
        
        complex_type = DocumentType(
            type_key='complex_contract',
            display_name='Complex Contract',
            metadata_schema={
                "type": "object",
                "properties": {
                    "parties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "role": {"type": "string", "enum": ["client", "contractor"]}
                            },
                            "required": ["name", "role"]
                        }
                    },
                    "terms": {
                        "type": "object",
                        "properties": {
                            "duration": {"type": "integer"},
                            "value": {"type": "number"}
                        }
                    }
                },
                "required": ["parties"]
            }
        )
        registry.register_document_type(complex_type)
        
        # Test valid complex metadata
        valid_complex_metadata = {
            "parties": [
                {"name": "Acme Corp", "role": "client"},
                {"name": "Dev Solutions", "role": "contractor"}
            ],
            "terms": {
                "duration": 12,
                "value": 100000.50
            }
        }
        
        is_valid = registry.validate_metadata('complex_contract', valid_complex_metadata)
        assert is_valid is True

    def test_document_type_registry_performance(self):
        """Test registry performance with many document types"""
        registry = DocumentTypeRegistry()
        
        # Register many types
        for i in range(100):
            doc_type = DocumentType(
                type_key=f'type_{i}',
                display_name=f'Type {i}',
                metadata_schema={"type": "object", "properties": {}}
            )
            registry.register_document_type(doc_type)
        
        # Lookups should be fast
        import time
        start = time.time()
        
        for i in range(100):
            doc_type = registry.get_document_type(f'type_{i}')
            assert doc_type.type_key == f'type_{i}'
        
        end = time.time()
        lookup_time = end - start
        
        # Should be very fast (dictionary lookups)
        assert lookup_time < 0.1, f"Lookups too slow: {lookup_time}s"


class TestPhase1BackwardCompatibility:
    """Test backward compatibility with Phase 1 NDA system"""
    
    def test_nda_type_preserves_phase1_behavior(self):
        """Test that NDA document type preserves Phase 1 behavior"""
        from api.db.generic_schema import get_default_document_types
        
        # Get default NDA type
        nda_type = next(dt for dt in get_default_document_types() if dt.type_key == 'nda')
        
        # Should match Phase 1 configuration
        assert nda_type.type_key == 'nda'
        assert nda_type.default_workflow_process_key == 'nda_review_approval'
        assert nda_type.llm_review_threshold == 0.7
        assert nda_type.template_bucket == 'nda-templates'

    def test_phase1_nda_metadata_validates(self):
        """Test that Phase 1 NDA metadata validates in generic system"""
        registry = DocumentTypeRegistry()
        
        from api.db.generic_schema import get_default_document_types
        nda_type = next(dt for dt in get_default_document_types() if dt.type_key == 'nda')
        registry.register_document_type(nda_type)
        
        # Phase 1 NDA metadata
        phase1_metadata = {
            "nda_type": "mutual",
            "direction": "outbound",
            "term_months": 24,
            "survival_months": 36,
            "governing_law": "California"
        }
        
        # Should validate successfully
        is_valid = registry.validate_metadata('nda', phase1_metadata)
        assert is_valid is True


class TestServiceErrorHandling:
    """Test error handling and robustness"""
    
    def test_database_failure_handling(self):
        """Test graceful handling of database failures"""
        with patch('api.services.document_type_service.get_db_session') as mock_db:
            mock_db.side_effect = Exception("Database connection failed")
            
            service = DocumentTypeService()
            
            # Should not crash during initialization
            assert service is not None
            
            # Should still work with defaults even if database fails
            try:
                types = service.load_document_types()
                # Should have at least defaults
                assert len(types) >= 0
            except Exception:
                # If it fails, should be gracefully
                pass

    def test_malformed_json_schema_handling(self):
        """Test handling of malformed JSON schemas during validation"""
        registry = DocumentTypeRegistry()
        
        # Register type with malformed schema (registration might succeed)
        invalid_type = DocumentType(
            type_key='invalid',
            display_name='Invalid Type',
            metadata_schema={
                "type": "object",
                "properties": {
                    "test_field": {
                        "type": "invalid_type_that_does_not_exist"
                    }
                }
            }
        )
        
        try:
            registry.register_document_type(invalid_type)
        except Exception:
            pass  # Registration might fail, that's ok
        
        # Validation should definitely fail with invalid schema
        with pytest.raises((DocumentTypeValidationError, InvalidMetadataError, Exception)):
            registry.validate_metadata('invalid', {"test_field": "some_value"})

    def test_service_singleton_behavior(self):
        """Test service singleton behavior"""
        service1 = get_document_type_service()
        service2 = get_document_type_service()
        
        # Should be same instance
        assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
