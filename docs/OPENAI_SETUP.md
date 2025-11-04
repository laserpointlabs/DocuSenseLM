# Setting Up OpenAI API

To use OpenAI instead of Ollama, you need to:

## 1. Update Environment Variables

Edit `.env` file and set:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your-api-key-here
```

Or if using Docker, update `docker-compose.yml` environment variables:

```yaml
environment:
  - LLM_PROVIDER=openai
  - OPENAI_API_KEY=${OPENAI_API_KEY}
```

## 2. Restart API Service

After updating the configuration:

```bash
docker-compose restart api
```

Or if running locally:
- Stop the API
- Export the environment variables:
  ```bash
  export LLM_PROVIDER=openai
  export OPENAI_API_KEY=your-api-key-here
  ```
- Restart the API

## 3. Verify Configuration

Check that the API is using OpenAI:

```bash
curl http://localhost:8000/admin/stats
```

The system will automatically use OpenAI when `LLM_PROVIDER=openai` is set.

## Default Model

The default OpenAI model is `gpt-3.5-turbo`. You can change it with:

```bash
OPENAI_MODEL=gpt-4
```
