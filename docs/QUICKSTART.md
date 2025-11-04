# Quick Start Guide

## One-Command Setup

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start all services
docker-compose up -d

# 3. Initialize database
docker-compose exec api python api/db/migrations/001_init_schema.py

# 4. (Optional) Seed sample data
docker-compose exec api python scripts/seed_data.py
```

## Access Points

- **UI**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

## Using Makefile

```bash
make setup    # Initial setup
make up       # Start services
make seed     # Load sample documents
make eval     # Run evaluation
make down     # Stop services
```

## First Steps

1. **Upload a document**: Go to Admin → Upload
2. **Search**: Go to Search → Enter query
3. **Ask a question**: Go to Ask Question → Enter question
4. **Test competency**: Go to Competency → Builder → Create questions

## Troubleshooting

- **Services not starting**: Check `docker-compose logs`
- **Database errors**: Run `make setup` again
- **LLM not working**: Ensure Ollama is running or set `OPENAI_API_KEY`
