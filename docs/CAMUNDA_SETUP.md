# Camunda 7 Setup Guide

This guide explains how to set up and use Camunda 7 for NDA workflow orchestration.

## Overview

Camunda 7 is used to orchestrate the NDA review and approval workflow. It manages:
- LLM review tasks (external tasks)
- Human review tasks (user tasks)
- Approval tasks (user tasks)
- Final approval tasks (user tasks)
- Workflow state management

## Docker Setup

Camunda is configured in `docker-compose.yml`:

```yaml
camunda:
  image: camunda/camunda-bpm-platform:7.20.0
  container_name: nda-camunda
  environment:
    - DB_DRIVER=org.postgresql.Driver
    - DB_URL=jdbc:postgresql://postgres:5432/nda_db
    - DB_USERNAME=nda_user
    - DB_PASSWORD=nda_password
  ports:
    - "8080:8080"  # REST API and Web UI
```

## Starting Camunda

```bash
docker compose up -d camunda
```

## Accessing Camunda

- **Web UI**: http://localhost:8080/camunda
- **REST API**: http://localhost:8080/engine-rest
- **Default credentials**: `demo` / `demo`

## BPMN Workflow

The NDA review workflow is defined in `camunda/bpmn/nda_review_approval.bpmn`.

### Workflow Steps

1. **Start Event**: NDA Received
2. **LLM Review** (External Task): Automated review by LLM
   - Topic: `llm_review`
   - Sets variable: `llm_approved` (boolean)
3. **Gateway**: LLM Approved?
   - If approved → Continue to Human Review
   - If rejected → End (Rejected)
4. **Human Review** (User Task): Internal reviewer reviews
   - Assignee: `reviewer_user_id`
   - Sets variable: `human_approved` (boolean)
5. **Gateway**: Human Approved?
   - If approved → Continue to Approval
   - If rejected → End (Rejected by Human)
6. **Approval** (User Task): Approver reviews
   - Assignee: `approver_user_id`
   - Sets variable: `approval_approved` (boolean)
7. **Gateway**: Approved?
   - If approved → Continue to Final Approval
   - If rejected → End (Rejected by Approver)
8. **Final Approval** (User Task): Final approver signs
   - Assignee: `final_approver_user_id`
9. **End Event**: Approved

### Process Variables

- `nda_record_id` (String): UUID of the NDA record
- `llm_approved` (Boolean): LLM review result
- `human_approved` (Boolean): Human review result
- `approval_approved` (Boolean): Approval result
- `reviewer_user_id` (String): User ID for human review task
- `approver_user_id` (String): User ID for approval task
- `final_approver_user_id` (String): User ID for final approval task

## Deploying BPMN Workflow

### Option 1: Via Web UI

1. Open http://localhost:8080/camunda
2. Navigate to "Processes" → "Deploy Process"
3. Upload `camunda/bpmn/nda_review_approval.bpmn`

### Option 2: Via REST API

```bash
curl -X POST \
  http://localhost:8080/engine-rest/deployment/create \
  -H "Content-Type: multipart/form-data" \
  -F "deployment-name=nda-review-approval" \
  -F "deployment-source=cli" \
  -F "nda_review_approval.bpmn=@camunda/bpmn/nda_review_approval.bpmn"
```

### Option 3: Automatic Deployment

BPMN files in `camunda/bpmn/` are mounted to Camunda's deployment directory and should be auto-deployed on startup.

## Using the Camunda Service

```python
from api.services.camunda_service import get_camunda_service

camunda = get_camunda_service()

# Start a process instance
result = camunda.start_process_instance(
    process_key="nda_review_approval",
    variables={
        "nda_record_id": "123e4567-e89b-12d3-a456-426614174000",
        "reviewer_user_id": "user-123",
        "approver_user_id": "user-456",
        "final_approver_user_id": "user-789",
    },
    business_key="NDA-12345",
)

process_instance_id = result["id"]
```

## External Task Worker

External tasks (like LLM review) are handled by workers that:
1. Poll Camunda for available tasks
2. Execute the task logic
3. Complete the task with results

See `api/workers/camunda_worker.py` for the worker implementation.

## Environment Variables

```bash
CAMUNDA_URL=http://camunda:8080    # Camunda REST API URL
CAMUNDA_USERNAME=demo              # Camunda username
CAMUNDA_PASSWORD=demo               # Camunda password
```

## Troubleshooting

### Camunda Not Starting

1. Check logs: `docker logs nda-camunda`
2. Verify PostgreSQL is running: `docker ps | grep postgres`
3. Check database connection settings in docker-compose.yml

### BPMN Not Deploying

1. Check file is in `camunda/bpmn/` directory
2. Verify file is valid BPMN 2.0 XML
3. Check Camunda logs for deployment errors
4. Try manual deployment via Web UI

### Process Instance Not Starting

1. Verify process is deployed: Check Camunda Web UI → Processes
2. Check process key matches: Should be `nda_review_approval`
3. Verify required variables are provided
4. Check Camunda logs for errors

## Testing

Test Camunda connectivity:

```python
from api.services.camunda_service import get_camunda_service

camunda = get_camunda_service()
if camunda.health_check():
    print("Camunda is accessible")
else:
    print("Camunda is not accessible")
```

## Next Steps

1. Deploy the BPMN workflow
2. Implement the external task worker for LLM review
3. Create API endpoints to start workflows and complete tasks
4. Build frontend UI for task management








