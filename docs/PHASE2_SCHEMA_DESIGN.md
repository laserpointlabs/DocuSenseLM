# Phase 2: Generic Legal Document Schema Design

## Overview

Phase 2 transforms our NDA-specific database schema into a **generic legal document workflow system** that can handle any document type while maintaining full backward compatibility with the NDA system we built in Phase 1.

## Current State (Phase 1)

✅ **Solid Foundation:**
- `NDARecord` table with NDA-specific fields
- `NDAWorkflowInstance` for workflow tracking  
- `NDATemplate` for template management
- Status schema with workflow support
- 98 tests ensuring everything works

## Phase 2 Goals

🎯 **Transform to Generic System:**
- Replace NDA-specific tables with generic `legal_documents`
- Add `document_types` configuration for different document types
- Generalize workflow tables to support any document workflow
- Maintain 100% backward compatibility
- Add support for new document types (service agreements, employment contracts, etc.)

## New Generic Schema Design

### 1. Core Document Table

```sql
-- Replace: nda_records 
-- With: legal_documents (supports any document type)
CREATE TABLE legal_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    
    -- Document type and classification
    document_type VARCHAR(50) NOT NULL,  -- 'nda', 'service_agreement', 'employment_contract'
    document_subtype VARCHAR(50),        -- 'mutual', 'unilateral', 'standard', 'custom'
    
    -- Generic party information  
    primary_party_name VARCHAR(255) NOT NULL,      -- Our company/organization
    counterparty_name VARCHAR(255) NOT NULL,       -- Other party
    counterparty_domain VARCHAR(255),
    counterparty_email VARCHAR(255),
    
    -- Generic dates and terms
    effective_date DATE,
    expiry_date DATE,
    
    -- Generic status (same as Phase 1 NDA statuses)
    status VARCHAR(30) NOT NULL DEFAULT 'created',
    
    -- Generic ownership and access
    owner_user_id UUID REFERENCES users(id),
    entity_id VARCHAR(255),  -- For multi-entity organizations
    
    -- File and content
    file_uri VARCHAR(512) NOT NULL,
    file_sha256 BYTEA NOT NULL UNIQUE,
    extracted_text TEXT,
    text_tsv TSVECTOR,
    
    -- Flexible document-type-specific metadata
    document_metadata JSONB DEFAULT '{}',  -- Store document-specific fields
    
    -- Workflow links (generalized)
    workflow_instance_id UUID,  -- Links to generic workflow table
    template_id UUID,
    template_version INTEGER,
    
    -- Audit and tags
    tags JSONB DEFAULT '{}',
    facts_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_legal_documents_status CHECK (
        status IN (
            'created', 'draft', 'in_review', 'pending_signature', 'customer_signed',
            'llm_reviewed_approved', 'llm_reviewed_rejected', 'reviewed', 
            'approved', 'rejected', 'signed', 'active', 'expired', 'terminated', 'archived'
        )
    )
);
```

**Key Features:**
- **Generic fields** work for any document type  
- **document_metadata JSONB** stores type-specific fields (NDA: term_months, Service Agreement: payment_terms)
- **Same status flow** as Phase 1 (no workflow changes needed)
- **Foreign keys preserved** (templates, workflows, users)

### 2. Document Type Configuration

```sql
-- New table: Configurable document types
CREATE TABLE document_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_key VARCHAR(50) UNIQUE NOT NULL,           -- 'nda', 'service_agreement' 
    display_name VARCHAR(100) NOT NULL,             -- 'Non-Disclosure Agreement'
    description TEXT,
    
    -- Schema definition for document_metadata JSONB field
    metadata_schema JSONB NOT NULL DEFAULT '{}',    -- JSON Schema for validation
    
    -- Workflow configuration
    default_workflow_process_key VARCHAR(100),      -- 'nda_review_approval'
    
    -- Review and validation settings
    llm_review_enabled BOOLEAN DEFAULT true,
    llm_review_threshold FLOAT DEFAULT 0.7,
    require_human_review BOOLEAN DEFAULT true,
    
    -- Template settings
    template_bucket VARCHAR(100) DEFAULT 'legal-templates',
    
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Pre-populated with:**
```sql
INSERT INTO document_types (type_key, display_name, metadata_schema, default_workflow_process_key) VALUES
('nda', 'Non-Disclosure Agreement', '{
    "type": "object",
    "properties": {
        "nda_type": {"type": "string", "enum": ["mutual", "unilateral"]},
        "direction": {"type": "string", "enum": ["inbound", "outbound"]}, 
        "term_months": {"type": "integer", "minimum": 1},
        "survival_months": {"type": "integer", "minimum": 0},
        "governing_law": {"type": "string"}
    }
}', 'nda_review_approval'),

('service_agreement', 'Service Agreement', '{
    "type": "object", 
    "properties": {
        "service_type": {"type": "string"},
        "contract_value": {"type": "number", "minimum": 0},
        "payment_terms": {"type": "string"},
        "deliverables": {"type": "array", "items": {"type": "string"}}
    }
}', 'service_agreement_approval');
```

### 3. Generalized Workflow Tables

```sql
-- Replace: nda_workflow_instances
-- With: document_workflow_instances (supports any document type)  
CREATE TABLE document_workflow_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_document_id UUID REFERENCES legal_documents(id) UNIQUE,
    document_type VARCHAR(50) NOT NULL,             -- Links to document_types.type_key
    camunda_process_instance_id VARCHAR(100) NOT NULL UNIQUE,
    process_key VARCHAR(100) NOT NULL,              -- BPMN process definition key
    current_status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Replace: nda_workflow_tasks  
-- With: document_workflow_tasks (supports any document type)
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

### 4. Generalized Template System

```sql
-- Replace: nda_templates
-- With: document_templates (supports any document type)
CREATE TABLE document_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type VARCHAR(50) NOT NULL REFERENCES document_types(type_key),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    file_path VARCHAR(512) NOT NULL,
    version INTEGER DEFAULT 1,
    template_key VARCHAR(255) NOT NULL,
    
    -- Template variable schema definition
    variable_schema JSONB DEFAULT '{}',             -- JSON Schema for template variables
    
    is_active BOOLEAN DEFAULT true,
    is_current BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    change_notes TEXT,
    
    CONSTRAINT uq_document_template_key_version UNIQUE (template_key, version)
);
```

## Migration Strategy (Backward Compatibility)

### Phase 2.1: Add New Tables Alongside Existing
- Create new generic tables
- Keep existing NDA tables functioning
- Dual-write to both systems during transition

### Phase 2.2: Data Migration
- Copy `nda_records` → `legal_documents` (document_type='nda')
- Copy `nda_templates` → `document_templates` (document_type='nda')  
- Copy `nda_workflow_instances` → `document_workflow_instances`
- Migrate NDA-specific metadata to `document_metadata` JSONB field

### Phase 2.3: API Compatibility Layer
- Keep existing `/workflow/nda/*` endpoints working
- Add new generic `/documents/*` endpoints
- Route NDA requests through compatibility layer

### Phase 2.4: Service Generalization
- Update services to use generic tables
- Add document type registry and validation
- Maintain NDA-specific behavior through configuration

## Benefits of This Design

### 1. **Scalability**
- Easy to add new document types (just add to `document_types`)
- Reuse all workflow, template, and email infrastructure
- Same codebase handles all document types

### 2. **Flexibility** 
- Document-specific metadata in JSONB (no schema changes needed)
- Configurable workflows per document type
- Type-specific validation rules

### 3. **Backward Compatibility**
- Existing NDA system continues working
- Gradual migration possible
- No disruption to current users

### 4. **Future-Proof**
- Ready for any document type
- Extensible configuration system
- Workflow engine supports multiple processes

## Phase 2 Implementation Plan

1. **2.1**: Design and test generic schema
2. **2.2**: Add document types configuration  
3. **2.3**: Generalize workflow tables
4. **2.4**: Create migration strategy
5. **2.5**: Implement data migration
6. **2.6**: Test complete generic system

**Ready to start Task 2.1: Design Generic Legal Document Schema + Tests!** 🧪
