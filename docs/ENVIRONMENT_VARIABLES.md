# Environment Variables Reference

This document describes all environment variables used by the NDA Tool application.

## Database Configuration

```bash
POSTGRES_URL=postgresql://nda_user:nda_password@postgres:5432/nda_db
POSTGRES_USER=nda_user
POSTGRES_PASSWORD=nda_password
POSTGRES_DB=nda_db
```

## Search & Vector Storage

```bash
OPENSEARCH_URL=http://opensearch:9200
OPENSEARCH_USER=admin
OPENSEARCH_PASS=admin123

QDRANT_URL=http://qdrant:6333
```

## Object Storage (MinIO/S3)

```bash
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

## LLM Configuration

```bash
# LLM Provider: ollama_local, ollama_network, openai
LLM_PROVIDER=ollama_local
LLM_ENDPOINT=http://ollama:11434

# Ollama-specific settings
OLLAMA_MODEL=llama3.2
OLLAMA_CONVERSATION_MODEL=llama3.2
OLLAMA_CONTEXT_LENGTH=4096
OLLAMA_KEEP_ALIVE=24h

# OpenAI (if using OpenAI provider)
OPENAI_API_KEY=

# LLM Features
ENABLE_LLM_REFINEMENT=false
LLM_EXTRACTION_MODEL=
```

## Embedding Model

```bash
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
```

## OCR Configuration

```bash
USE_TEXTRACT=false  # true for AWS Textract, false for Tesseract
```

## Email Configuration

Email settings can be configured via environment variables (preferred) or through the database `email_config` table.

### SMTP Settings (for sending emails)

```bash
EMAIL_SMTP_HOST=mailhog                    # SMTP server hostname
EMAIL_SMTP_PORT=1025                       # SMTP port (587 for TLS, 465 for SSL, 1025 for MailHog)
EMAIL_SMTP_USER=                            # SMTP username (optional for MailHog)
EMAIL_SMTP_PASSWORD=                       # SMTP password (optional for MailHog)
EMAIL_SMTP_USE_TLS=false                   # Use TLS (true/false)
```

### IMAP Settings (for receiving emails)

```bash
EMAIL_IMAP_HOST=                            # IMAP server hostname (e.g., imap.gmail.com)
EMAIL_IMAP_PORT=993                        # IMAP port (993 for SSL, 143 for non-SSL)
EMAIL_IMAP_USER=                            # IMAP username
EMAIL_IMAP_PASSWORD=                       # IMAP password
EMAIL_IMAP_USE_SSL=true                     # Use SSL (true/false)
```

### Email Sender Settings

```bash
EMAIL_FROM_ADDRESS=nda-system@example.com   # Default sender email address
EMAIL_FROM_NAME=NDA Management System      # Default sender name
```

### Email Poller Settings

```bash
EMAIL_POLLER_ENABLED=true                  # Enable/disable email polling worker
EMAIL_POLL_INTERVAL=60                     # Poll interval in seconds
```

### Email Security

```bash
EMAIL_ENCRYPTION_KEY=                      # Base64-encoded Fernet key for password encryption
                                           # If not set, a key is auto-generated (not persistent)
```

**Note**: For production, set `EMAIL_ENCRYPTION_KEY` to a persistent value. Generate a key with:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## Workflow Configuration

### Camunda BPMN Engine

```bash
CAMUNDA_URL=http://camunda:8080            # Camunda REST API URL
CAMUNDA_USERNAME=demo                      # Camunda username
CAMUNDA_PASSWORD=demo                      # Camunda password
```

### LLM Review Settings

```bash
WORKFLOW_LLM_REVIEW_ENABLED=true           # Enable LLM review of signed NDAs
WORKFLOW_LLM_APPROVAL_THRESHOLD=0.7        # LLM approval confidence threshold (0.0-1.0)
```

## Cloudflare Tunnel (Optional)

```bash
CLOUDFLARE_TUNNEL_TOKEN=                    # Cloudflare Tunnel token
CLOUDFLARE_DOMAIN_UI=ui.yourdomain.com      # UI domain
CLOUDFLARE_DOMAIN_API=api.yourdomain.com    # API domain
```

## Example .env File

```bash
# Database
POSTGRES_USER=nda_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=nda_db

# Email (using MailHog for local development)
EMAIL_SMTP_HOST=mailhog
EMAIL_SMTP_PORT=1025
EMAIL_SMTP_USE_TLS=false
EMAIL_FROM_ADDRESS=nda-system@example.com
EMAIL_FROM_NAME=NDA Management System
EMAIL_POLLER_ENABLED=true
EMAIL_POLL_INTERVAL=60

# Email (using Gmail for production)
# EMAIL_SMTP_HOST=smtp.gmail.com
# EMAIL_SMTP_PORT=587
# EMAIL_SMTP_USER=your-email@gmail.com
# EMAIL_SMTP_PASSWORD=your-app-password
# EMAIL_SMTP_USE_TLS=true
# EMAIL_IMAP_HOST=imap.gmail.com
# EMAIL_IMAP_PORT=993
# EMAIL_IMAP_USER=your-email@gmail.com
# EMAIL_IMAP_PASSWORD=your-app-password
# EMAIL_IMAP_USE_SSL=true

# Workflow
CAMUNDA_URL=http://camunda:8080
CAMUNDA_USERNAME=demo
CAMUNDA_PASSWORD=demo
WORKFLOW_LLM_REVIEW_ENABLED=true
WORKFLOW_LLM_APPROVAL_THRESHOLD=0.7

# Generate a persistent encryption key for production
# EMAIL_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

## Priority

When both environment variables and database configuration exist:
1. **Environment variables** take precedence
2. Database `email_config` table is used as fallback

This allows easy configuration via `.env` files while maintaining backward compatibility with database-stored configurations.








