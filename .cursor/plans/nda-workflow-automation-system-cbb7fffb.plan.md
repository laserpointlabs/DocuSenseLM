<!-- cbb7fffb-1938-494c-86ff-5292587f4c8f 3727403b-2419-4e52-9405-30bc66e1776b -->
# NDA Workflow Automation System Implementation Plan

## Overview

This plan implements a complete automated NDA workflow system that allows admins to create unsigned NDAs from templates, send them to customers via email, process customer responses, perform LLM-based initial reviews, and manage internal approval workflows using Camunda 7.

## Architecture Components

### 1. Database Schema Extensions

**New Tables:**

- `nda_templates` - Store NDA template definitions (name, description, file_path, is_active, created_at)
- `nda_workflow_instances` - Track Camunda workflow instances (nda_record_id, camunda_process_instance_id, current_status, started_at)
- `nda_workflow_tasks` - Track workflow tasks (workflow_instance_id, task_id, assignee_user_id, status, due_date, completed_at)
- `email_config` - Email server configuration (smtp_host, smtp_port, smtp_user, smtp_password, imap_host, imap_port, from_address, encrypted_password)
- `workflow_config` - Workflow configuration (reviewer_user_ids JSON array, approver_user_ids JSON array, final_approver_user_id, llm_review_enabled)
- `email_messages` - Track sent/received emails (nda_record_id, message_id, direction, subject, body, attachments JSON, sent_at, received_at)
- `nda_audit_log` - Audit trail for all NDA actions (nda_record_id, user_id, action, details JSON, timestamp)

**Schema Updates:**

- Update `NDARecord.status` constraint to include new statuses: `created`, `customer_signed`, `llm_reviewed_approved`, `llm_reviewed_rejected`, `reviewed`, `approved`, `rejected`, `archived`, `expired`, `active`, `draft`, `negotiating`, `signed`, `terminated`
- Add `workflow_instance_id` foreign key to `nda_records` table

**Files:**

- `api/db/schema.py` - Add new tables and update NDARecord
- `api/db/migrations/` - Create Alembic migration

### 2. Email Service Layer

**Components:**

- `api/services/email_service.py` - Email sending/receiving service
  - SMTP sending with attachments
  - IMAP receiving and parsing
  - Email template rendering
  - Attachment extraction (PDF/DOCX)

- `api/services/email_parser.py` - Parse incoming emails
  - Extract attachments
  - Identify NDA-related emails by subject/body patterns
  - Link emails to NDA records via tracking IDs

**Dependencies:**

- `aiosmtplib` for async SMTP
- `imaplib` for IMAP (or `aioimaplib` for async)
- `email` library for parsing

**Files:**

- `api/services/email_service.py`
- `api/services/email_parser.py`
- `requirements.txt` - Add email dependencies

### 3. NDA Template Management

**Components:**

- Template storage in MinIO bucket `nda-templates`
- Template rendering service using `python-docx` to fill placeholders
- Template variables: `{counterparty_name}`, `{effective_date}`, `{term_months}`, `{governing_law}`, etc.

**Files:**

- `api/services/template_service.py` - Template management and rendering
- `api/routers/templates.py` - Template CRUD endpoints
- `api/models/requests.py` - Template request models

### 4. Camunda 7 Integration

**Components:**

- `api/services/camunda_service.py` - Camunda REST API client
  - Start process instances
  - Complete external tasks
  - Query process instances
  - Handle task assignments

- External task worker pattern:
  - Poll Camunda for external tasks
  - Execute task logic (e.g., send email, update status)
  - Complete tasks via REST API

**BPMN Workflow Design:**

- Process: `nda_review_approval`
- Tasks:
  - `llm_review` (external) - LLM performs initial review
  - `human_review` (user task) - Internal reviewer reviews
  - `approval` (user task) - Approver reviews
  - `final_approval` (user task) - Final approver signs
  - `rejection` (end event) - Handle rejections
  - `approval_complete` (end event) - Workflow complete

**Files:**

- `api/services/camunda_service.py`
- `api/workers/camunda_worker.py` - Background worker for external tasks
- `bpmn/nda_review_approval.bpmn` - BPMN workflow definition
- `docker-compose.yml` - Add Camunda 7 service

### 5. LLM Review Service

**Components:**

- `api/services/llm_review_service.py` - LLM-based NDA review
  - Extract text from signed NDA
  - Compare against template/standard clauses
  - Identify changes, risks, compliance issues
  - Return approval/rejection with reasoning

- Integration with existing `llm/` module

**Files:**

- `api/services/llm_review_service.py`
- `llm/prompts.py` - Add NDA review prompts

### 6. Workflow Management API

**Endpoints:**

- `POST /workflow/nda/create` - Create unsigned NDA from template
- `POST /workflow/nda/{nda_id}/send` - Send NDA to customer
- `POST /workflow/nda/{nda_id}/process-email` - Process incoming email
- `GET /workflow/nda/{nda_id}/status` - Get workflow status
- `POST /workflow/nda/{nda_id}/update-status` - Admin manual status update
- `POST /workflow/tasks/{task_id}/complete` - Complete workflow task
- `GET /workflow/tasks` - List pending tasks for user

**Files:**

- `api/routers/workflow.py` - Workflow endpoints
- `api/models/requests.py` - Workflow request models
- `api/models/responses.py` - Workflow response models

### 7. Admin Management UI

**Components:**

- Email configuration management
- Workflow configuration (reviewers, approvers)
- Template management
- NDA workflow dashboard
- Task assignment interface

**Files:**

- `ui/app/workflow/page.tsx` - Workflow dashboard
- `ui/app/workflow/[id]/page.tsx` - Individual NDA workflow view
- `ui/app/admin/email-config/page.tsx` - Email configuration
- `ui/app/admin/workflow-config/page.tsx` - Workflow configuration
- `ui/app/admin/templates/page.tsx` - Template management
- `ui/components/NDACreationModal.tsx` - Create NDA modal
- `ui/components/WorkflowTaskList.tsx` - Task list component
- `ui/components/EmailConfigForm.tsx` - Email config form

### 8. Background Workers

**Components:**

- Email polling worker - Periodically check IMAP for new emails
- Camunda external task worker - Poll and process external tasks
- Workflow status sync worker - Keep workflow status in sync

**Files:**

- `api/workers/email_poller.py` - Email polling worker
- `api/workers/camunda_worker.py` - Camunda task worker
- `api/main.py` - Register background workers on startup

### 9. Docker Compose Updates

**New Services:**

- `camunda` - Camunda 7 BPMN engine (official Docker image)
- Update `api` service to include new dependencies

**Files:**

- `docker-compose.yml` - Add Camunda service

## Implementation Phases

### Phase 1: Foundation (Database & Email)

1. Create database migrations for new tables
2. Implement email service (SMTP sending)
3. Implement email parser (IMAP receiving)
4. Add email configuration management

### Phase 2: Template System

1. Template storage and management
2. Template rendering service
3. Template CRUD API
4. Admin UI for templates

### Phase 3: NDA Creation & Sending

1. NDA creation modal/form
2. Template filling service
3. Email sending integration
4. NDA record creation with `created` status

### Phase 4: Email Processing

1. Email polling worker
2. Email-to-NDA linking logic
3. Attachment extraction and processing
4. Status update to `customer_signed`

### Phase 5: Camunda Integration

1. Set up Camunda 7 service
2. Create BPMN workflow definition
3. Implement Camunda REST client
4. External task worker implementation

### Phase 6: LLM Review

1. LLM review service
2. Integration with workflow
3. Status updates (`llm_reviewed_approved`/`llm_reviewed_rejected`)

### Phase 7: Workflow Management

1. Workflow API endpoints
2. Task assignment and completion
3. Status management
4. Admin manual override

### Phase 8: UI Components

1. Workflow dashboard
2. NDA creation modal
3. Task management interface
4. Admin configuration pages

### Phase 9: Testing & Refinement

1. End-to-end workflow testing
2. Email integration testing
3. Camunda workflow testing
4. Error handling and edge cases

## Key Files to Create/Modify

**Backend:**

- `api/db/schema.py` - Schema updates
- `api/db/migrations/versions/XXXX_add_workflow_tables.py` - Migration
- `api/services/email_service.py` - Email service
- `api/services/email_parser.py` - Email parsing
- `api/services/template_service.py` - Template management
- `api/services/camunda_service.py` - Camunda integration
- `api/services/llm_review_service.py` - LLM review
- `api/routers/workflow.py` - Workflow endpoints
- `api/routers/templates.py` - Template endpoints
- `api/workers/email_poller.py` - Email worker
- `api/workers/camunda_worker.py` - Camunda worker

**Frontend:**

- `ui/app/workflow/page.tsx` - Workflow dashboard
- `ui/app/workflow/[id]/page.tsx` - NDA detail view
- `ui/app/admin/email-config/page.tsx` - Email config
- `ui/app/admin/workflow-config/page.tsx` - Workflow config
- `ui/app/admin/templates/page.tsx` - Templates
- `ui/components/NDACreationModal.tsx` - Creation modal
- `ui/components/WorkflowTaskList.tsx` - Task list

**Infrastructure:**

- `docker-compose.yml` - Add Camunda service
- `bpmn/nda_review_approval.bpmn` - BPMN workflow
- `requirements.txt` - Add email dependencies

## Status Flow

```
created → customer_signed → llm_reviewed_approved → reviewed → approved → active
                              ↓
                    llm_reviewed_rejected → rejected
                    
Admin can manually set: created, customer_signed, reviewed, approved, rejected, archived, expired, active
```

## Security Considerations

- Encrypt email passwords in database
- Secure Camunda REST API access
- Validate email attachments (virus scanning)
- Audit all status changes
- Role-based access control for workflow actions

## Dependencies to Add

- `aiosmtplib` - Async SMTP
- `aioimaplib` - Async IMAP (or use `imaplib` with threading)
- `python-docx` - DOCX template rendering (may already exist)
- `python-camunda-client` or `requests` for Camunda REST API

### To-dos

- [ ] Create database schema extensions: nda_templates, nda_workflow_instances, nda_workflow_tasks, email_config, workflow_config, email_messages, nda_audit_log tables. Update NDARecord status constraint.
- [ ] Implement email service for SMTP sending and IMAP receiving with attachment handling
- [ ] Build template management system: storage, rendering with python-docx, CRUD API
- [ ] Create NDA creation modal/form and API endpoint to generate unsigned NDAs from templates
- [ ] Implement email sending workflow: send filled NDA to customer with tracking
- [ ] Build email polling worker and parser to detect customer-signed NDAs and update status
- [ ] Set up Camunda 7 service in docker-compose and create BPMN workflow definition
- [ ] Implement Camunda REST API client and external task worker for workflow orchestration
- [ ] Build LLM review service to analyze signed NDAs and return approval/rejection decisions
- [ ] Create workflow management API endpoints for status updates, task completion, and admin overrides
- [ ] Build workflow dashboard, NDA creation modal, task management interface, and admin configuration pages
- [ ] Test end-to-end workflow: create NDA → send email → receive signed → LLM review → workflow → approval