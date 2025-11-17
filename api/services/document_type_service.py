"""
Document Type Configuration Service

Manages document type configurations and validation:
- Document type registry (memory cache)
- JSON Schema validation for document metadata
- Default document type configurations
- Workflow configuration per document type
- LLM review settings per type
- Template bucket configuration
- Performance optimization with caching

Supports all document types: NDAs, Service Agreements, Employment Contracts, etc.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    import jsonschema
    from jsonschema import ValidationError, SchemaError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    ValidationError = Exception
    SchemaError = Exception

from api.db import get_db_session
from api.db.generic_schema import DocumentType, get_default_document_types

logger = logging.getLogger(__name__)


class DocumentTypeNotFoundError(Exception):
    """Raised when a document type is not found"""
    pass


class DocumentTypeValidationError(Exception):
    """Raised when document type configuration is invalid"""
    pass


class InvalidMetadataError(Exception):
    """Raised when document metadata fails validation"""
    pass


class DocumentTypeRegistry:
    """
    Registry for document type configurations with validation and caching
    
    Provides fast lookups and validation for document types without hitting database
    """

    def __init__(self):
        self._types: Dict[str, DocumentType] = {}
        self._last_loaded = None
        self._cache_timeout = 300  # 5 minutes

    def register_document_type(self, document_type: DocumentType):
        """Register a document type in the registry"""
        # Validate the document type configuration
        self._validate_document_type_config(document_type)
        
        # Store in registry
        self._types[document_type.type_key] = document_type
        logger.info(f"Registered document type: {document_type.type_key} ({document_type.display_name})")

    def get_document_type(self, type_key: str) -> DocumentType:
        """Get document type by key"""
        if type_key not in self._types:
            raise DocumentTypeNotFoundError(f"Document type '{type_key}' not found")
        
        return self._types[type_key]

    def list_document_types(self, active_only: bool = True) -> List[DocumentType]:
        """List all registered document types"""
        types = list(self._types.values())
        
        if active_only:
            types = [dt for dt in types if getattr(dt, 'is_active', True)]
        
        return types

    def get_workflow_process_key(self, type_key: str) -> str:
        """Get workflow process key for document type"""
        doc_type = self.get_document_type(type_key)
        return doc_type.default_workflow_process_key

    def get_llm_review_config(self, type_key: str) -> Dict[str, Any]:
        """Get LLM review configuration for document type"""
        doc_type = self.get_document_type(type_key)
        return {
            'enabled': doc_type.llm_review_enabled,
            'threshold': doc_type.llm_review_threshold,
            'require_human_review': doc_type.require_human_review
        }

    def validate_metadata(self, type_key: str, metadata: Optional[Dict[str, Any]]) -> bool:
        """
        Validate document metadata against document type schema
        
        Uses JSON Schema validation if available, falls back to basic validation
        """
        if metadata is None:
            metadata = {}
        
        doc_type = self.get_document_type(type_key)
        schema = doc_type.metadata_schema
        
        if not schema or schema == {}:
            # No schema means no validation required
            return True
        
        if JSONSCHEMA_AVAILABLE:
            try:
                jsonschema.validate(metadata, schema)
                return True
            except ValidationError as e:
                raise InvalidMetadataError(f"Metadata validation failed for {type_key}: {e.message}")
            except SchemaError as e:
                raise DocumentTypeValidationError(f"Invalid schema for {type_key}: {e.message}")
        else:
            # Fallback validation without jsonschema library
            return self._basic_metadata_validation(schema, metadata, type_key)

    def _validate_document_type_config(self, document_type: DocumentType):
        """Validate document type configuration"""
        if not document_type.type_key:
            raise DocumentTypeValidationError("Document type must have type_key")
        
        if not document_type.display_name:
            raise DocumentTypeValidationError("Document type must have display_name")
        
        # Validate metadata schema is valid JSON Schema (if jsonschema available)
        if JSONSCHEMA_AVAILABLE and document_type.metadata_schema:
            try:
                # Test the schema by creating a validator
                jsonschema.Draft7Validator(document_type.metadata_schema)
            except SchemaError as e:
                raise DocumentTypeValidationError(f"Invalid metadata schema: {e.message}")
            except Exception as e:
                raise DocumentTypeValidationError(f"Invalid metadata schema: {str(e)}")
        elif document_type.metadata_schema and not isinstance(document_type.metadata_schema, dict):
            # Basic validation when jsonschema not available
            raise DocumentTypeValidationError("Metadata schema must be a valid JSON object")

    def _basic_metadata_validation(self, schema: Dict[str, Any], metadata: Dict[str, Any], type_key: str) -> bool:
        """
        Basic metadata validation when jsonschema library is not available
        
        Provides minimal validation for required fields and basic types
        """
        try:
            # Check required fields
            required_fields = schema.get('required', [])
            for field in required_fields:
                if field not in metadata:
                    raise InvalidMetadataError(f"Required field '{field}' missing for {type_key}")
            
            # Check basic property types
            properties = schema.get('properties', {})
            for field, value in metadata.items():
                if field in properties:
                    field_schema = properties[field]
                    expected_type = field_schema.get('type')
                    
                    if expected_type == 'string' and not isinstance(value, str):
                        raise InvalidMetadataError(f"Field '{field}' must be string for {type_key}")
                    elif expected_type == 'integer' and not isinstance(value, int):
                        raise InvalidMetadataError(f"Field '{field}' must be integer for {type_key}")
                    elif expected_type == 'number' and not isinstance(value, (int, float)):
                        raise InvalidMetadataError(f"Field '{field}' must be number for {type_key}")
                    elif expected_type == 'boolean' and not isinstance(value, bool):
                        raise InvalidMetadataError(f"Field '{field}' must be boolean for {type_key}")
                    elif expected_type == 'array' and not isinstance(value, list):
                        raise InvalidMetadataError(f"Field '{field}' must be array for {type_key}")
            
            return True
            
        except Exception as e:
            if isinstance(e, InvalidMetadataError):
                raise
            raise InvalidMetadataError(f"Metadata validation failed for {type_key}: {str(e)}")


class DocumentTypeService:
    """
    Service for managing document type configurations
    
    Provides high-level interface for document type management with caching,
    validation, and database integration.
    """

    def __init__(self):
        self.registry = DocumentTypeRegistry()
        self._initialized = False
        self._last_cache_clear = time.time()

    def _ensure_initialized(self):
        """Ensure document types are loaded from database"""
        if not self._initialized:
            try:
                self._load_from_database()
            except Exception as e:
                logger.debug(f"Database load failed (expected in Phase 2): {e}")
            
            # Always load defaults (even if database load succeeded)
            try:
                self._load_defaults() 
                logger.debug(f"After loading defaults, registry has {len(self.registry._types)} types")
            except Exception as e:
                logger.error(f"Failed to load defaults: {e}")
            self._initialized = True

    def _load_from_database(self):
        """Load document types from database"""
        db = get_db_session()
        try:
            document_types = db.query(DocumentType).filter(DocumentType.is_active == True).all()
            
            for doc_type in document_types:
                self.registry.register_document_type(doc_type)
            
            logger.info(f"Loaded {len(document_types)} document types from database")
            
        except Exception as e:
            logger.error(f"Failed to load document types from database: {e}")
            # Don't fail initialization - we can use defaults
        finally:
            db.close()

    def _load_defaults(self):
        """Load default document type configurations"""
        try:
            default_types = get_default_document_types()
            loaded_count = 0
            
            for doc_type in default_types:
                # Only register if not already loaded from database
                try:
                    self.registry.get_document_type(doc_type.type_key)
                    # Already exists, skip
                    logger.debug(f"Document type {doc_type.type_key} already loaded from database")
                except DocumentTypeNotFoundError:
                    # Doesn't exist, register default
                    self.registry.register_document_type(doc_type)
                    loaded_count += 1
            
            if loaded_count > 0:
                logger.info(f"Loaded {loaded_count} default document type configurations")
            
        except Exception as e:
            logger.error(f"Failed to load default document types: {e}")
            # Still register defaults even if some fail
            try:
                default_types = get_default_document_types()
                for doc_type in default_types:
                    try:
                        self.registry.register_document_type(doc_type)
                    except Exception:
                        pass  # Skip invalid defaults
            except Exception:
                pass

    def load_document_types(self) -> List[DocumentType]:
        """Load and return all document types"""
        self._ensure_initialized()
        return self.registry.list_document_types()

    def get_document_type(self, type_key: str) -> DocumentType:
        """Get document type by key"""
        self._ensure_initialized()
        return self.registry.get_document_type(type_key)

    def list_document_types(self, active_only: bool = True) -> List[DocumentType]:
        """List document types with optional filtering"""
        self._ensure_initialized()
        return self.registry.list_document_types(active_only=active_only)

    def validate_metadata(self, type_key: str, metadata: Optional[Dict[str, Any]]) -> bool:
        """Validate document metadata against type schema"""
        self._ensure_initialized()
        return self.registry.validate_metadata(type_key, metadata)

    def get_workflow_process_key(self, type_key: str) -> str:
        """Get workflow process key for document type"""
        self._ensure_initialized()
        return self.registry.get_workflow_process_key(type_key)

    def get_llm_review_config(self, type_key: str) -> Dict[str, Any]:
        """Get LLM review configuration for document type"""
        self._ensure_initialized()
        return self.registry.get_llm_review_config(type_key)

    def clear_cache(self):
        """Clear cached document types (force reload from database)"""
        self._types = {}
        self._initialized = False
        self._last_cache_clear = time.time()
        logger.info("Document type cache cleared")

    def refresh_configuration(self):
        """Refresh document type configuration from database"""
        self.clear_cache()
        self._ensure_initialized()

    def get_template_bucket(self, type_key: str) -> str:
        """Get template bucket for document type"""
        doc_type = self.get_document_type(type_key)
        return doc_type.template_bucket or 'legal-templates'

    def supports_document_type(self, type_key: str) -> bool:
        """Check if document type is supported"""
        self._ensure_initialized()
        try:
            self.registry.get_document_type(type_key)
            return True
        except DocumentTypeNotFoundError:
            return False

    def get_validation_schema(self, type_key: str) -> Dict[str, Any]:
        """Get JSON Schema for document type metadata validation"""
        doc_type = self.get_document_type(type_key)
        return doc_type.metadata_schema

    def get_document_type_config(self, type_key: str) -> Dict[str, Any]:
        """Get complete configuration for document type (for API responses)"""
        doc_type = self.get_document_type(type_key)
        
        return {
            'type_key': doc_type.type_key,
            'display_name': doc_type.display_name,
            'description': doc_type.description,
            'metadata_schema': doc_type.metadata_schema,
            'workflow_process_key': doc_type.default_workflow_process_key,
            'llm_review': {
                'enabled': doc_type.llm_review_enabled,
                'threshold': doc_type.llm_review_threshold,
                'require_human_review': doc_type.require_human_review
            },
            'template_bucket': doc_type.template_bucket,
            'is_active': doc_type.is_active
        }

    # Performance monitoring methods
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        return {
            'types_cached': len(self.registry._types),
            'last_cache_clear': self._last_cache_clear,
            'cache_age_seconds': time.time() - self._last_cache_clear,
            'initialized': self._initialized
        }


# Global service instance
_document_type_service: Optional[DocumentTypeService] = None


def get_document_type_service() -> DocumentTypeService:
    """Get or create document type service instance (singleton)"""
    global _document_type_service
    if _document_type_service is None:
        _document_type_service = DocumentTypeService()
    return _document_type_service


def create_document_type_service() -> DocumentTypeService:
    """Create new document type service instance (for testing)"""
    return DocumentTypeService()


# Convenience functions for common operations
def validate_document_metadata(type_key: str, metadata: Dict[str, Any]) -> bool:
    """Validate document metadata (convenience function)"""
    service = get_document_type_service()
    return service.validate_metadata(type_key, metadata)


def get_workflow_process_key(type_key: str) -> str:
    """Get workflow process key for document type (convenience function)"""
    service = get_document_type_service()
    return service.get_workflow_process_key(type_key)


def get_document_type_llm_config(type_key: str) -> Dict[str, Any]:
    """Get LLM configuration for document type (convenience function)"""
    service = get_document_type_service()
    return service.get_llm_review_config(type_key)


def is_document_type_supported(type_key: str) -> bool:
    """Check if document type is supported (convenience function)"""
    service = get_document_type_service()
    return service.supports_document_type(type_key)
