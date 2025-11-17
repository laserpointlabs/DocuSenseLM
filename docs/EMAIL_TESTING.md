# Email System Testing Guide

This guide explains how to test the email system locally using MailHog.

## Prerequisites

1. Docker and docker-compose installed
2. MailHog service running (included in docker-compose.yml)
3. Database and storage services running

## Setup

### 1. Start MailHog

MailHog is already configured in `docker-compose.yml`. Start it with:

```bash
docker-compose up -d mailhog
```

MailHog provides:
- **SMTP Server**: `localhost:1025` (or `mailhog:1025` from within Docker network)
- **Web UI**: http://localhost:8025

### 2. Configure Email Settings

Run the setup script to create a test email configuration:

```bash
python scripts/setup_test_email_config.py
```

This creates an email config named "test_mailhog" that:
- Uses MailHog SMTP server (no authentication required)
- Sends from `nda-system@example.com`
- Is automatically set as active

### 3. Test Email Sending

Run the comprehensive test script:

```bash
python scripts/test_email_system.py
```

This will:
1. Set up email configuration
2. Test basic email sending
3. Create a test NDA
4. Send NDA via email
5. Test email parsing

### 4. View Sent Emails

Open http://localhost:8025 in your browser to see all emails sent through MailHog.

## Manual Testing

### Test Email Sending via API

1. Create an NDA using `/workflow/nda/create`
2. Send it via email using `/workflow/nda/{nda_id}/send`
3. Check MailHog UI to see the email

Example:

```bash
# Create NDA
curl -X POST http://localhost:8000/workflow/nda/create \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "template-uuid",
    "counterparty_name": "Test Company",
    "counterparty_email": "test@example.com"
  }'

# Send NDA email
curl -X POST http://localhost:8000/workflow/nda/{nda_id}/send \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "to_addresses": ["customer@example.com"],
    "subject": "Test NDA"
  }'
```

### Test Email Polling

Since MailHog doesn't support IMAP, email polling is simulated. For testing:

1. Use the manual polling endpoint: `POST /workflow/email/poll`
2. Or simulate receiving emails by directly inserting into the database

## Email Poller

The email poller runs automatically when the API starts (if `EMAIL_POLLER_ENABLED=true`).

- **Poll Interval**: Configurable via `EMAIL_POLL_INTERVAL` (default: 60 seconds)
- **Disable**: Set `EMAIL_POLLER_ENABLED=false` in environment

The poller:
1. Checks IMAP inbox for new messages
2. Links emails to NDAs via tracking ID or content matching
3. Processes attachments (PDF/DOCX)
4. Updates NDA status to `customer_signed` when signed version received
5. Queues document ingestion

## Testing Workflow

### Complete End-to-End Test

1. **Create NDA**:
   ```bash
   POST /workflow/nda/create
   ```

2. **Send NDA Email**:
   ```bash
   POST /workflow/nda/{nda_id}/send
   ```
   - Check MailHog UI to verify email sent
   - Note the tracking ID

3. **Simulate Customer Reply** (since MailHog doesn't support IMAP):
   - Manually create an email message record in database
   - Or use the test script to simulate receiving

4. **Check Status**:
   ```bash
   GET /workflow/nda/{nda_id}/status
   ```
   - Should show status updated to `customer_signed`

## Troubleshooting

### Email Not Sending

1. Check MailHog is running: `docker ps | grep mailhog`
2. Verify email config is active in database
3. Check API logs for errors
4. Verify SMTP host is `mailhog` (not `localhost`) when running in Docker

### Email Poller Not Working

1. Check `EMAIL_POLLER_ENABLED` environment variable
2. Check API logs for poller startup messages
3. Verify IMAP configuration (if using real email server)
4. Note: MailHog doesn't support IMAP, so polling won't work with MailHog

### Testing with Real Email Server

To test with a real email server (Gmail, Outlook, etc.):

1. Update email config via admin UI or database
2. Set IMAP settings:
   - Gmail: `imap.gmail.com:993` (SSL)
   - Outlook: `outlook.office365.com:993` (SSL)
3. Use app-specific password for authentication
4. Enable email poller

## Environment Variables

- `EMAIL_POLLER_ENABLED`: Enable/disable email poller (default: `true`)
- `EMAIL_POLL_INTERVAL`: Poll interval in seconds (default: `60`)
- `EMAIL_ENCRYPTION_KEY`: Base64-encoded key for password encryption (optional, auto-generated if not set)








