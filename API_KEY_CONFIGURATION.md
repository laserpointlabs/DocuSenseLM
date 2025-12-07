# OpenAI API Key Configuration

## Overview

DocuSenseLM now supports configuring your OpenAI API key through the application's settings interface. The API key is stored securely in your local configuration file and is never transmitted to any external server (except OpenAI's API).

## How to Configure

### Method 1: Using the Settings UI (Recommended)

1. **Launch DocuSenseLM**
2. **Navigate to Settings** (gear icon in the sidebar)
3. **Find the "OpenAI API Key" section** at the top of the settings page
4. **Enter your API key** in the input field
   - The key will be hidden by default (shown as `•••`)
   - Click the eye icon to reveal/hide the key
5. **Click "Save API Key"**
6. You should see a confirmation: ✓ API key is configured (sk-••••...••••)

### Method 2: Editing config.yaml Directly

1. **Navigate to Settings**
2. **Expand "Configuration Editor"**
3. **Select `config.yaml`** from the dropdown
4. **Find the `api` section** (at the top of the file):
   ```yaml
   api:
     openai_api_key: ""  # Add your OpenAI API key here
   ```
5. **Add your key between the quotes**:
   ```yaml
   api:
     openai_api_key: "sk-your-actual-api-key-here"
   ```
6. **Click "Save Changes"**

## Getting an API Key

1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
2. Log in or create an account
3. Click "Create new secret key"
4. Copy the key (you won't be able to see it again!)
5. Paste it into DocuSenseLM

## Security

### How Your API Key is Stored

- **Location**: `~/.config/docusenselm/config.yaml` (Linux) or equivalent on Windows/Mac
- **Format**: Plain text in YAML format
- **File Permissions**: Only readable by your user account
- **Never Sent**: The key is only sent to OpenAI's API, never to any other server

### Key Masking

When you view your configuration through the API or UI:
- The full key is **never displayed**
- Only the first 4 and last 4 characters are shown: `sk-ab...xyz`
- This helps verify the key is set without exposing the full value

## How It Works

1. **Priority Order**:
   - Environment variable `OPENAI_API_KEY` (highest priority)
   - Config file `api.openai_api_key`
   - If neither is set, features requiring OpenAI will be disabled

2. **Automatic Reinitialization**:
   - When you save a new API key, the OpenAI client automatically reinitializes
   - No need to restart the application

3. **Features Using the API Key**:
   - **Document Processing**: Extracting information from uploaded PDFs
   - **Chat Interface**: Answering questions about your documents
   - **RAG (Retrieval Augmented Generation)**: Semantic search using embeddings
   - **Competency Questions**: Auto-filling document metadata

## Troubleshooting

### "API key not configured" Warning

**Solution**: Add your API key using one of the methods above

### Features Not Working After Setting Key

1. **Verify the key is saved**:
   - Go to Settings
   - Check for the green checkmark: ✓ API key is configured
   - Verify the masked key looks correct

2. **Check the key is valid**:
   - Make sure you copied the entire key (starts with `sk-`)
   - Try creating a new key on OpenAI Platform

3. **Check logs**:
   - Open Developer Tools (Ctrl+Shift+I)
   - Look for errors related to OpenAI

### "Insufficient Quota" or "Invalid API Key" Errors

**These are from OpenAI**, not DocuSenseLM:
- **Insufficient Quota**: Add credits to your OpenAI account
- **Invalid API Key**: The key may be revoked or incorrect
- **Rate Limit**: You're making too many requests - wait a moment

## Using Environment Variables (Alternative)

For advanced users or deployment scenarios:

```bash
# Linux/Mac
export OPENAI_API_KEY="sk-your-key-here"
./DocuSenseLM-1.0.0.AppImage

# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-your-key-here"
.\DocuSenseLM.exe
```

Environment variables take priority over the config file.

## Backup and Restore

Your API key is included in backups created through the Settings page:
- **Backup**: Click "Download Backup" to create a ZIP file
- **Restore**: Click "Restore from Backup" and select your ZIP file

⚠️ **Warning**: Backup files contain your API key in plain text. Store them securely!

## FAQ

**Q: Can I use different API keys for different features?**
A: Not currently. One key is used for all OpenAI API calls.

**Q: Does the app store my API key in the cloud?**
A: No. It's only stored locally on your computer.

**Q: What if I don't want to use OpenAI?**
A: You can still use the app for document storage and metadata tracking. The chat and auto-extraction features won't work without an API key.

**Q: Can I share my configuration with my team?**
A: Yes, but **remove your API key first** or each team member should use their own key.

## Cost Considerations

OpenAI charges for API usage based on:
- **Tokens processed** (input + output)
- **Model used** (currently using GPT-4 for chat, embedding models for RAG)

Typical costs for DocuSenseLM:
- **Document processing**: ~$0.01-0.05 per document (varies by size)
- **Chat queries**: ~$0.001-0.01 per query
- **Embeddings**: ~$0.0001 per document

Monitor your usage at: https://platform.openai.com/usage

