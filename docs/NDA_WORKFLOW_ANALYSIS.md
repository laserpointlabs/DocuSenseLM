# NDA Workflow System Analysis

## Current State Summary

### What Exists

1. **Template Management** ✅
   - `NDATemplate` table with versioning
   - Template service for rendering DOCX templates
   - Template CRUD API endpoints
   - Templates stored in MinIO/S3 bucket `nda-templates`

2. **NDA Creation** ✅
   - `/workflow/nda/create` endpoint creates NDA from template
   - Renders template with variables (counterparty_name, dates, etc.)
   - Converts DOCX → PDF
   - Creates `NDARecord` with status `"created"`
   - Stores PDF in `nda-raw` bucket

3. **Email Service** ✅
   - SMTP sending configured
   - IMAP receiving configured
   - Email tracking with `tracking_id`
   - Email messages stored in `email_messages` table

4. **Email Sending** ⚠️ (Partially Working)
   - `/workflow/nda/{nda_id}/send` endpoint exists
   - Sends NDA PDF to customer
   - Generates tracking ID
   - **BUT**: Doesn't integrate with workflow
   - **BUT**: Doesn't update status properly

5. **Email Receiving** ⚠️ (Partially Working)
   - `EmailPoller` worker polls IMAP inbox
   - Processes attachments
   - Links emails to NDAs via tracking ID
   - Updates status to `"customer_signed"`
   - **BUT**: Doesn't trigger workflow properly

6. **Camunda Workflow** ⚠️ (Structurally Wrong)
   - BPMN workflow exists: `nda_review_approval.bpmn`
   - Camunda service integrated
   - External task workers exist
   - **BUT**: Workflow flow is backwards (see issues below)

7. **LLM Review** ✅
   - `LLMReviewService` exists
   - Can review NDAs
   - Returns approval/rejection with reasoning

---

## Critical Structural Issues

### Issue #1: Workflow Starts Correctly, But Status Management is Wrong ❌

**Current Flow:**
```
1. Create NDA → status: "created"
2. Auto-start workflow (if enabled) → status: "customer_signed" ❌ WRONG STATUS!
3. LLM reviews UNSIGNED document ✅ CORRECT (pre-send quality control)
4. Human reviews UNSIGNED document ✅ CORRECT (pre-send validation)
5. Send to customer (should be workflow step) → status should be "pending_signature"
6. Customer signs and returns → status: "customer_signed"
7. LLM reviews SIGNED document ✅ CORRECT (post-signature validation)
8. Human reviews SIGNED document ✅ CORRECT
9. Internal signature
10. Complete → status: "signed" or "active"
```

**Problems:**
- Line 345 in `workflow.py`: Sets status to `"customer_signed"` when workflow starts
- But NDA hasn't been sent to customer yet!
- Status should be `"llm_review"` or `"human_review"` during pre-send review
- Status should be `"pending_signature"` after sending
- Status should be `"customer_signed"` only when customer actually signs

**Correct Status Flow Should Be:**
```
1. Create NDA → status: "created"
2. Start workflow → status: "llm_review" (or "in_review")
3. LLM reviews UNSIGNED → status: "llm_reviewed_approved" or "llm_reviewed_rejected"
4. Human reviews UNSIGNED → status: "reviewed"
5. Send to customer (workflow step) → status: "pending_signature"
6. Customer signs and returns → status: "customer_signed"
7. LLM reviews SIGNED → status: "llm_reviewed_approved" or "llm_reviewed_rejected"
8. Human reviews SIGNED → status: "reviewed"
9. Internal signature → status: "signed" or "active"
```

### Issue #2: BPMN Workflow Structure is Actually Correct ✅ (But Implementation May Be Wrong)

**Current BPMN Flow:**
```
Start → LLM Review (unsigned) → Human Review → Send to Customer → Wait for Signature → LLM Review (signed) → Internal Signature → End
```

**Why This Makes Sense:**
1. **Pre-Send Review (Unsigned)** ✅ **INTENTIONAL AND VALUABLE**
   - Validates template rendering (correct names, dates, fields filled)
   - Catches template errors (even lawyer-written templates can have mistakes)
   - Ensures what we send is correct before customer sees it
   - Quality control: verify all placeholders replaced correctly
   - Legal compliance: ensure template was rendered properly

2. **Post-Signature Review (Signed)** ✅ **ALSO VALUABLE**
   - Validates customer didn't make problematic changes
   - Compares signed version to what we sent
   - Catches unauthorized modifications
   - Ensures final document is acceptable

**This is a Two-Stage Review Process:**
- **Stage 1: Pre-Send Quality Control** (unsigned document)
  - LLM validates template rendering
  - Human double-checks before sending
  - Prevents sending incorrect documents
  
- **Stage 2: Post-Signature Validation** (signed document)
  - LLM compares signed vs. sent version
  - Human reviews customer changes
  - Ensures final document is acceptable

**The BPMN Structure is Correct!** The issue is likely in:
- Status management (status doesn't reflect workflow state)
- Workflow start timing (starts too early with wrong status)
- Implementation details (reviews may not be working properly)

### Issue #3: Status Management is Confused ❌

**Current Status Values:**
- `"created"` - NDA created from template ✅
- `"customer_signed"` - Used incorrectly (set when workflow starts, not when customer signs) ❌
- `"llm_reviewed_approved"` - LLM approved ✅
- `"llm_reviewed_rejected"` - LLM rejected ✅
- `"reviewed"` - Human reviewed ✅
- `"approved"` - Approved ✅
- `"signed"` - Fully signed ✅

**Problems:**
- `"customer_signed"` status set incorrectly (line 345, 671, 1135, 1428, 1944)
- No status for "sent to customer" or "pending signature"
- Status changes don't align with workflow steps

**Correct Status Flow:**
```
"created" → NDA created from template
"draft" → NDA being edited internally
"pending_signature" → Sent to customer, waiting for signature
"customer_signed" → Customer returned signed NDA
"llm_reviewed_approved" → LLM approved signed document
"llm_reviewed_rejected" → LLM rejected signed document
"reviewed" → Human reviewed
"approved" → Approved internally
"rejected" → Rejected internally
"signed" → Fully executed (both parties signed)
"active" → Active and in effect
"expired" → Expired
"terminated" → Terminated early
```

### Issue #4: Email Sending Not Integrated with Workflow ❌

**Current:**
- `/workflow/nda/{nda_id}/send` is a standalone endpoint
- Manual step, not part of workflow
- Doesn't trigger workflow automatically
- Status doesn't change to "sent" or "pending_signature"

**Should Be:**
- Sending should be a workflow step (external task)
- Or sending should automatically start workflow
- Status should update to "pending_signature"
- Workflow should wait for customer signature

### Issue #5: Email Receiving Doesn't Trigger Workflow Properly ❌

**Current:**
- Email poller receives signed NDA
- Updates status to "customer_signed"
- Creates document record
- **BUT**: Doesn't trigger workflow or Camunda message event

**Should Be:**
- Email poller should trigger Camunda message event `CustomerSignedMessage`
- This should resume workflow from "Wait for Customer Signature" step
- Or start workflow if not started yet

---

## Proposed Correct Architecture

### Phase 1: NDA Creation (No Workflow Yet)
```
1. Admin creates NDA from template
   - POST /workflow/nda/create
   - Status: "created"
   - No workflow started yet

2. (Optional) Internal pre-review
   - Manual review before sending
   - Status: "draft" or stays "created"
```

### Phase 2: Send to Customer (Start Workflow)
```
1. Admin sends NDA to customer
   - POST /workflow/nda/{nda_id}/send
   - Status: "pending_signature"
   - START WORKFLOW HERE ✅
   - Workflow waits at "Wait for Customer Signature" step

2. Email sent with tracking ID
   - Email stored in email_messages table
   - Tracking ID links email to NDA
```

### Phase 3: Customer Signs (Resume Workflow)
```
1. Customer signs and returns NDA via email
   - Email poller receives email with attachment
   - Links to NDA via tracking ID
   - Uploads signed PDF as new document
   - Status: "customer_signed"
   - TRIGGER CAMUNDA MESSAGE EVENT ✅
   - Workflow resumes from "Wait for Customer Signature"

2. Workflow continues automatically
   - LLM reviews signed document
   - Human reviews signed document
   - Internal signature
   - Complete
```

### Correct BPMN Workflow Structure (Already Correct!)

```
Start Event: NDA Created
  ↓
LLM Review Unsigned Document (External Task) ✅ Pre-send quality control
  ↓
Gateway: LLM Approved Unsigned?
  ├─ No → End: Rejected (don't send incorrect document)
  └─ Yes ↓
Human Review Unsigned (User Task) ✅ Pre-send validation
  ↓
Gateway: Human Approved Unsigned?
  ├─ No → End: Rejected (don't send incorrect document)
  └─ Yes ↓
Send to Customer (External Task) ✅ Only send if approved
  ↓
Intermediate Catch Event: Wait for Customer Signature (Message Event)
  ↓ (resumes when message received)
LLM Review Signed Document (External Task) ✅ Post-signature validation
  ↓
Gateway: LLM Approved Signed?
  ├─ No → End: Rejected (customer made unacceptable changes)
  └─ Yes ↓
Human Review Signed (User Task) ✅ Post-signature review
  ↓
Gateway: Human Approved Signed?
  ├─ No → End: Rejected
  └─ Yes ↓
Internal Signature (User Task)
  ↓
End: Approved & Active
```

**This structure is correct!** The workflow properly:
1. Reviews unsigned document before sending (quality control)
2. Only sends if approved
3. Waits for customer signature
4. Reviews signed document after customer returns it
5. Completes if acceptable

---

## What Needs to Be Fixed

### 1. Fix Status Management
- Remove incorrect `"customer_signed"` status assignments
- Add `"pending_signature"` status
- Update status flow to match actual workflow

### 2. Fix Workflow Start Timing
- Don't start workflow on NDA creation
- Start workflow when sending to customer
- Or start workflow when customer signs (if not started)

### 3. Verify BPMN Workflow Implementation
- ✅ BPMN structure is correct (pre-send + post-signature reviews)
- Ensure LLM review of unsigned document actually validates template rendering
- Ensure "Send to Customer" step updates status to "pending_signature"
- Ensure message event properly triggers workflow resume
- Verify both review stages are working correctly

### 4. Integrate Email Sending with Workflow
- Make sending a workflow step (external task)
- Or automatically start workflow when sending
- Update status to "pending_signature"

### 5. Fix Email Receiving Workflow Trigger
- Email poller should trigger Camunda message event
- Use `CustomerSignedMessage` to resume workflow
- Ensure workflow instance is found and resumed

### 6. Fix Status Updates Throughout Workflow
- Each workflow step should update NDA status appropriately
- Status should reflect current state accurately
- Status changes should be logged in audit log

---

## Recommended Implementation Order

1. **Fix Status Management** (Foundation)
   - Update status constraint in schema
   - Fix all status assignments (remove incorrect "customer_signed" on workflow start)
   - Add "pending_signature" status
   - Add "llm_review" or "in_review" status for pre-send review phase
   - Ensure status reflects actual workflow state at each step

2. **Fix Workflow Start Logic**
   - ✅ Keep auto-start on creation (this is correct!)
   - Fix status assignment (don't set "customer_signed" on start)
   - Set appropriate status for pre-send review phase

3. **Verify BPMN Workflow Implementation**
   - ✅ BPMN structure is correct (keep as-is)
   - Ensure LLM review of unsigned validates template rendering properly
   - Ensure "Send to Customer" step updates status correctly
   - Fix message event handling for customer signature

4. **Integrate Email Sending with Workflow**
   - Ensure "Send to Customer" external task actually sends email
   - Update status to "pending_signature" when sent
   - Verify email tracking works

5. **Fix Email Receiving**
   - Trigger Camunda message event when customer signs
   - Resume workflow from "Wait for Customer Signature" step
   - Update status to "customer_signed" when received

6. **Enhance Pre-Send Review**
   - ✅ Fallback review already checks for unfilled placeholders (line 305-309 in `llm_review_service.py`)
   - Enhance LLM prompt for pre-send review to specifically check:
     - All template placeholders replaced correctly (e.g., `{counterparty_name}`, `{effective_date}`)
     - Names match counterparty name from NDA record
     - Dates are valid and properly formatted
     - Required fields filled (no empty placeholders)
     - Template structure intact (no broken formatting)
     - Legal entity names are correct
   - Differentiate between unsigned review (template validation) and signed review (change detection)
   - Ensure human review can catch template errors visually

7. **Test End-to-End**
   - Create NDA → Pre-send Review → Send → Customer Signs → Post-signature Review → Approve → Complete

---

## Key Files to Modify

1. `api/routers/workflow.py` - Fix status assignments (remove incorrect "customer_signed" on workflow start)
2. `camunda/bpmn/nda_review_approval.bpmn` - ✅ Structure is correct, no changes needed
3. `api/db/schema.py` - Update status constraint, add "pending_signature" status
4. `api/workers/email_poller.py` - Add Camunda message event trigger when customer signs
5. `api/workers/camunda_worker.py` - Verify external task handlers work correctly
6. `api/services/llm_review_service.py` - Enhance prompts to differentiate unsigned (template validation) vs signed (change detection) reviews
7. `api/routers/workflow.py` - Ensure "Send to Customer" external task updates status correctly

---

## Questions to Answer

1. **Should workflow start when sending to customer, or when customer signs?**
   - Recommendation: Start when sending, wait at message event

2. **Do we need internal pre-review before sending?**
   - Current: No pre-review step
   - Recommendation: Make it optional

3. **What happens if customer sends signed NDA but workflow hasn't started?**
   - Current: Creates document, updates status
   - Recommendation: Auto-start workflow if not started

4. **Should sending be a workflow step or separate action?**
   - Current: Separate endpoint
   - Recommendation: Can be either, but must start workflow

