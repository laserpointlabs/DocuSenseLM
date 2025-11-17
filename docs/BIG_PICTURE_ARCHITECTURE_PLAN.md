# Big Picture Architecture Plan: Legal Document Workflow System

## Executive Summary

The current "NDA Tool" is actually the foundation for a **Legal Document Workflow System** that can handle multiple document types. While currently focused on NDAs, the architecture should be generalized to support:

- **Service Agreements**
- **Employment Contracts** 
- **Sales/Purchase Agreements**
- **Partnership Agreements**
- **Licensing Agreements**
- **MSAs (Master Service Agreements)**
- **SOWs (Statements of Work)**
- And more...

## Current State Assessment

### ✅ Strong Foundation (Already Generic)

1. **Document Storage System**
   - `Document` table is generic
   - `DocumentChunk` supports any document type
   - MinIO/S3 storage is document-agnostic
   - Text extraction works for any PDF/DOCX

2. **Workflow Engine** 
   - Camunda BPMN engine supports any process
   - External task pattern is flexible
   - Variable passing system is generic

3. **Template System**
   - DOCX template rendering works for any document
   - `template_key` concept allows categorization
   - Version management is generic
   - Storage in MinIO is flexible

4. **Email System**
   - SMTP/IMAP infrastructure is generic
   - Tracking system works for any document
   - Attachment handling is flexible

5. **LLM Review System**
   - LLM client can analyze any document type
   - Review framework is adaptable
   - Confidence scoring is generic

6. **User Management & Security**
   - Role-based access control
   - Audit logging
   - JWT authentication

### ❌ NDA-Specific Components (Need Generalization)

1. **Database Schema**
   - `NDARecord` table is NDA-specific
   - `NDAWorkflowInstance`, `NDAWorkflowTask` are NDA-specific
   - `NDATemplate` table is NDA-specific
   - Field names like `counterparty_name`, `term_months`, `survival_months`

2. **API Layer**
   - Routes like `/workflow/nda/create`
   - Request/response models are NDA-specific
   - Business logic assumes NDA structure

3. **Workflow Processes**
   - Single `nda_review_approval.bpmn` process
   - Hard-coded for NDA workflow
   - NDA-specific variables and tasks

4. **Review Logic**
   - LLM prompts assume NDA structure
   - Validation rules are NDA-specific
   - Status flow assumes NDA lifecycle

## Proposed Architecture: Legal Document Workflow System

### Phase 1: Fix Current NDA System (Foundation)
*Timeline: 1-2 weeks*

**Immediate Priority**: Fix the NDA workflow to work correctly before generalization.

#### 1.1 Status Management Fix
```sql
-- Add missing statuses to constraint
ALTER TABLE nda_records DROP CONSTRAINT chk_nda_records_status;
ALTER TABLE nda_records ADD CONSTRAINT chk_nda_records_status CHECK (
    status IN (
        'created', 'draft', 'in_review', 'pending_signature', 
        'customer_signed', 'llm_reviewed_approved', 'llm_reviewed_rejected',
        'reviewed', 'approved', 'rejected', 'signed', 
        'active', 'expired', 'terminated'
    )
);
```

#### 1.2 Workflow Start Logic Fix
- Remove incorrect `status = "customer_signed"` on workflow start
- Set `status = "in_review"` when workflow starts
- Update status properly at each workflow step

#### 1.3 Email Integration Fix  
- Ensure "Send to Customer" external task actually sends email
- Update status to `"pending_signature"` when sent
- Trigger Camunda message event when customer signs

#### 1.4 Enhanced Pre-Send Review
- Improve LLM prompts for template validation
- Add template-specific checks (placeholders, dates, names)
- Differentiate unsigned vs signed review prompts

### Phase 2: Generalize Schema (Data Model)
*Timeline: 2-3 weeks*

#### 2.1 Create Generic Document Schema

```sql
-- Generic legal document table
CREATE TABLE legal_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    document_type VARCHAR(50) NOT NULL, -- 'nda', 'service_agreement', 'employment_contract', etc.
    
    -- Generic party information
    primary_party_name VARCHAR(255) NOT NULL,    -- Our company
    counterparty_name VARCHAR(255) NOT NULL,     -- Other party
    counterparty_domain VARCHAR(255),
    counterparty_email VARCHAR(255),
    
    -- Generic dates
    effective_date DATE,
    expiry_date DATE,
    
    -- Generic document metadata
    status VARCHAR(50) NOT NULL DEFAULT 'created',
    owner_user_id UUID REFERENCES users(id),
    
    -- File information
    file_uri VARCHAR(512) NOT NULL,
    file_sha256 BYTEA NOT NULL UNIQUE,
    extracted_text TEXT,
    text_tsv TSVECTOR,
    
    -- Flexible metadata for document-type-specific fields
    document_metadata JSONB, -- Store NDA-specific fields like term_months, survival_months
    
    -- Workflow links
    workflow_instance_id UUID,
    template_id UUID,
    template_version INTEGER,
    
    -- Audit fields
    tags JSONB DEFAULT '{}',
    facts_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document type definitions
CREATE TABLE document_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_key VARCHAR(50) UNIQUE NOT NULL, -- 'nda', 'service_agreement', etc.
    display_name VARCHAR(100) NOT NULL,   -- 'Non-Disclosure Agreement'
    description TEXT,
    
    -- Schema definition for document_metadata
    metadata_schema JSONB, -- JSON Schema defining expected fields
    
    -- Default workflow process key
    default_workflow_process_key VARCHAR(100),
    
    -- Review settings
    llm_review_enabled BOOLEAN DEFAULT true,
    llm_review_threshold FLOAT DEFAULT 0.7,
    
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 2.2 Generalize Workflow Tables

```sql
-- Generic workflow instances
CREATE TABLE document_workflow_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_document_id UUID REFERENCES legal_documents(id) UNIQUE,
    document_type VARCHAR(50) NOT NULL,
    camunda_process_instance_id VARCHAR(100) NOT NULL UNIQUE,
    process_key VARCHAR(100) NOT NULL, -- BPMN process definition key
    current_status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Generic workflow tasks  
CREATE TABLE document_workflow_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_instance_id UUID REFERENCES document_workflow_instances(id),
    task_id VARCHAR(100) NOT NULL UNIQUE,
    task_name VARCHAR(255) NOT NULL,
    assignee_user_id UUID REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'pending',
    due_date TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### 2.3 Generalize Template System

```sql
-- Generic document templates
CREATE TABLE document_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type VARCHAR(50) NOT NULL, -- Links to document_types.type_key
    name VARCHAR(255) NOT NULL,
    description TEXT,
    file_path VARCHAR(512) NOT NULL, -- MinIO path
    version INTEGER DEFAULT 1,
    template_key VARCHAR(255) NOT NULL, -- e.g., 'standard-mutual-nda', 'basic-service-agreement'
    
    -- Template variable definitions
    variable_schema JSONB, -- JSON Schema defining template variables
    
    is_active BOOLEAN DEFAULT true,
    is_current BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    change_notes TEXT
);
```

### Phase 3: Generalize Business Logic (Services & APIs)
*Timeline: 3-4 weeks*

#### 3.1 Generic Document Service

```python
class DocumentWorkflowService:
    """Generic service for managing legal documents of any type"""
    
    async def create_document(
        self,
        document_type: str,
        template_id: str,
        template_data: Dict[str, Any],
        user_id: str,
        auto_start_workflow: bool = True
    ) -> LegalDocument:
        """Create document from template - works for any document type"""
        pass
    
    async def start_workflow(
        self,
        document_id: str,
        workflow_config: Optional[Dict[str, Any]] = None
    ) -> WorkflowInstance:
        """Start appropriate workflow for document type"""
        pass
    
    async def send_to_counterparty(
        self,
        document_id: str,
        email_addresses: List[str],
        message: Optional[str] = None
    ) -> str:
        """Send document to counterparty - generic for any document type"""
        pass
```

#### 3.2 Generic API Endpoints

```python
# Generic document endpoints
@router.post("/documents", response_model=DocumentSummary)
async def create_document(request: DocumentCreateRequest):
    """Create any type of legal document from template"""
    
@router.post("/documents/{document_id}/send")
async def send_document(document_id: str, request: SendDocumentRequest):
    """Send document to counterparty"""
    
@router.post("/documents/{document_id}/workflow/start") 
async def start_workflow(document_id: str, request: StartWorkflowRequest):
    """Start workflow for document"""

# Document-type-specific endpoints (for complex operations)
@router.post("/documents/nda", response_model=DocumentSummary)
async def create_nda(request: NDACreateRequest):
    """Create NDA with NDA-specific validation and defaults"""
```

#### 3.3 Document Type Registry

```python
class DocumentTypeRegistry:
    """Registry of document types and their configurations"""
    
    def register_document_type(
        self,
        type_key: str,
        display_name: str,
        metadata_schema: Dict[str, Any],
        workflow_process_key: str,
        review_config: Dict[str, Any]
    ):
        """Register a new document type"""
        pass
    
    def get_document_type(self, type_key: str) -> DocumentTypeConfig:
        """Get configuration for document type"""
        pass
    
    def get_workflow_process_key(self, type_key: str) -> str:
        """Get BPMN process key for document type"""
        pass

# Pre-register document types
registry = DocumentTypeRegistry()
registry.register_document_type(
    type_key="nda",
    display_name="Non-Disclosure Agreement", 
    metadata_schema={
        "type": "object",
        "properties": {
            "term_months": {"type": "integer"},
            "survival_months": {"type": "integer"},
            "nda_type": {"type": "string", "enum": ["mutual", "one_way"]},
            "governing_law": {"type": "string"}
        }
    },
    workflow_process_key="nda_review_approval",
    review_config={
        "llm_enabled": True,
        "llm_threshold": 0.7,
        "require_legal_review": True
    }
)
```

### Phase 4: Multi-Process Workflow System
*Timeline: 2-3 weeks*

#### 4.1 Document-Type-Specific BPMN Processes

```
camunda/bpmn/
├── nda_review_approval.bpmn           # Existing NDA process
├── service_agreement_approval.bpmn    # Service agreement process  
├── employment_contract_approval.bpmn  # Employment contract process
└── generic_document_approval.bpmn     # Fallback for new document types
```

#### 4.2 Configurable Workflow Steps

```python
class WorkflowConfigurationService:
    """Configure workflow steps per document type"""
    
    def get_workflow_config(self, document_type: str) -> WorkflowConfig:
        """Get workflow configuration for document type"""
        return {
            "process_key": "nda_review_approval",
            "pre_send_review": {
                "llm_enabled": True,
                "human_review_required": True,
                "auto_approve_threshold": 0.9
            },
            "post_signature_review": {
                "llm_enabled": True, 
                "human_review_required": False,
                "change_detection_enabled": True
            },
            "approval_chain": [
                {"role": "legal_reviewer", "required": True},
                {"role": "approver", "required": True},
                {"role": "signer", "required": True}
            ]
        }
```

#### 4.3 Dynamic External Task Routing

```python
class GenericCamundaWorker:
    """Generic worker that routes tasks based on document type"""
    
    async def process_llm_review_task(self, task: Dict[str, Any]):
        """Route LLM review to appropriate document type handler"""
        document_type = task["variables"]["document_type"]["value"]
        handler = self.get_review_handler(document_type)
        return await handler.review_document(task)
    
    def get_review_handler(self, document_type: str) -> DocumentReviewHandler:
        """Get document-type-specific review handler"""
        handlers = {
            "nda": NDAReviewHandler(),
            "service_agreement": ServiceAgreementReviewHandler(),
            "employment_contract": EmploymentContractReviewHandler()
        }
        return handlers.get(document_type, GenericReviewHandler())
```

### Phase 5: Enhanced Review & Validation System  
*Timeline: 2-3 weeks*

#### 5.1 Document-Type-Specific LLM Prompts

```python
class DocumentReviewService:
    """Generic document review with type-specific logic"""
    
    def get_review_prompt(
        self, 
        document_type: str, 
        review_stage: str,  # 'pre_send' or 'post_signature'
        document_data: Dict[str, Any]
    ) -> str:
        """Get appropriate review prompt based on document type and stage"""
        
        prompt_templates = {
            "nda": {
                "pre_send": "Review this NDA template rendering for accuracy...",
                "post_signature": "Compare this signed NDA to the original..."
            },
            "service_agreement": {
                "pre_send": "Review this service agreement for completeness...",
                "post_signature": "Validate customer changes to service agreement..."
            }
        }
        
        return self.render_prompt_template(
            prompt_templates[document_type][review_stage],
            document_data
        )
```

#### 5.2 Configurable Validation Rules

```python
class DocumentValidationEngine:
    """Configurable validation rules per document type"""
    
    def validate_document(
        self, 
        document_type: str, 
        document_content: str,
        metadata: Dict[str, Any]
    ) -> ValidationResult:
        """Run validation rules specific to document type"""
        
        validators = self.get_validators(document_type)
        results = []
        
        for validator in validators:
            result = validator.validate(document_content, metadata)
            results.append(result)
        
        return ValidationResult(results)
    
    def get_validators(self, document_type: str) -> List[DocumentValidator]:
        """Get validators for document type"""
        base_validators = [
            PlaceholderValidator(),  # Check for unfilled {placeholders}
            BasicStructureValidator()  # Check document structure
        ]
        
        type_specific = {
            "nda": [
                NDATermValidator(),      # Validate NDA-specific terms
                ConfidentialityValidator()  # Check confidentiality clauses
            ],
            "service_agreement": [
                ServiceScopeValidator(), # Validate service scope
                PaymentTermsValidator()  # Check payment terms
            ]
        }
        
        return base_validators + type_specific.get(document_type, [])
```

### Phase 6: Migration Strategy
*Timeline: 1-2 weeks*

#### 6.1 Backward Compatibility

```python
# Keep existing NDA-specific endpoints working
@router.post("/workflow/nda/create")  # Legacy endpoint
async def create_nda_legacy(request: NDACreateRequest):
    """Legacy NDA creation - redirect to generic endpoint"""
    generic_request = DocumentCreateRequest(
        document_type="nda",
        template_id=request.template_id,
        metadata={
            "counterparty_name": request.counterparty_name,
            "term_months": request.term_months,
            "survival_months": request.survival_months,
            # ... map other fields
        }
    )
    return await create_document(generic_request)
```

#### 6.2 Data Migration Script

```sql
-- Migrate NDARecord to legal_documents
INSERT INTO legal_documents (
    id, document_id, document_type, primary_party_name, counterparty_name,
    counterparty_domain, effective_date, expiry_date, status, owner_user_id,
    file_uri, file_sha256, extracted_text, text_tsv,
    document_metadata, workflow_instance_id, template_id, template_version,
    tags, facts_json, created_at, updated_at
)
SELECT 
    id, document_id, 'nda' as document_type, 
    'Your Company' as primary_party_name, counterparty_name,
    counterparty_domain, effective_date, expiry_date, status, owner_user_id,
    file_uri, file_sha256, extracted_text, text_tsv,
    jsonb_build_object(
        'nda_type', nda_type,
        'direction', direction,
        'term_months', term_months,
        'survival_months', survival_months
    ) as document_metadata,
    workflow_instance_id, template_id, template_version,
    tags, facts_json, created_at, updated_at
FROM nda_records;
```

## Benefits of This Architecture

### 1. **Scalability**
- Easy to add new document types
- Configurable workflows per document type
- Reusable components across document types

### 2. **Maintainability** 
- Single codebase for all document types
- Shared business logic
- Centralized configuration

### 3. **Flexibility**
- Document-type-specific validation rules
- Configurable approval workflows  
- Customizable review processes

### 4. **Consistency**
- Same user experience across document types
- Unified audit trail
- Consistent status management

### 5. **Future-Proof**
- Easy to add new document types
- Extensible validation system
- Configurable workflow engine

## Implementation Priority

### Immediate (Next 2 weeks)
1. **Fix current NDA issues** - Get existing system working correctly
2. **Status management** - Fix the foundation
3. **Email integration** - Complete the workflow loop

### Short Term (1-2 months)  
4. **Database generalization** - Migrate to generic schema
5. **API generalization** - Create generic endpoints
6. **Service layer generalization** - Generic document services

### Medium Term (2-4 months)
7. **Multi-process workflows** - Add new document type workflows
8. **Enhanced validation** - Document-type-specific rules
9. **Advanced review system** - Sophisticated LLM analysis

### Long Term (4+ months)
10. **UI generalization** - Generic document management UI
11. **Advanced features** - Document comparison, automated negotiation
12. **Integration** - External system APIs, e-signature services

## Success Metrics

### Technical Metrics
- **Code reuse**: >80% shared code across document types
- **Performance**: <2s document creation time
- **Reliability**: >99.5% workflow completion rate

### Business Metrics  
- **Time to market**: New document type in <1 week
- **Processing time**: <24h average document turnaround
- **Error rate**: <1% template/workflow errors

### User Experience Metrics
- **Ease of use**: Same interface for all document types
- **Consistency**: Unified status tracking
- **Flexibility**: Custom workflows per business need

---

## Questions for Product Decision

1. **Document Type Priority**: What document types should we support first after NDAs?
2. **Workflow Complexity**: How complex should the configurable workflows be?
3. **Migration Timeline**: Should we fix NDA issues first or generalize immediately?
4. **Backward Compatibility**: How long should we maintain NDA-specific APIs?
5. **Resource Allocation**: What team size/timeline do we have for this transformation?

This architecture positions the system as a comprehensive **Legal Document Workflow Platform** rather than just an "NDA Tool", while maintaining all current functionality and fixing existing issues.
