# Data Persistence Guide

## Overview

The NDA Tool uses Docker volumes to persist data across container restarts. Your uploaded files, database records, search indices, and vector embeddings are stored in persistent volumes.

## Persistent Volumes

The following volumes are configured in `docker-compose.yml`:

- **`postgres_data`** - PostgreSQL database (documents, metadata, chunks)
- **`minio_data`** - MinIO object storage (uploaded PDF/DOCX files)
- **`opensearch_data`** - OpenSearch indices (BM25 search)
- **`qdrant_data`** - Qdrant vectors (semantic search embeddings)
- **`ollama_data`** - Ollama models (downloaded LLM models)

## Safe Restart Commands

### ✅ Safe - Preserves Data

```bash
# Restart specific containers (preserves volumes)
docker compose restart ollama api

# Stop and start (preserves volumes)
docker compose stop
docker compose start

# Recreate containers with new config (preserves volumes)
docker compose up -d --force-recreate api
```

### ⚠️  Dangerous - May Lose Data

```bash
# ❌ DO NOT USE - Removes volumes and ALL data
docker compose down -v

# ❌ DO NOT USE - Deletes specific volume
docker volume rm ndatool_postgres_data

# ❌ DO NOT USE - Removes everything including volumes
docker compose down --volumes --remove-orphans
```

## Checking Data Persistence

### Check Database Documents
```bash
docker exec nda-postgres psql -U nda_user -d nda_db -c "SELECT COUNT(*) FROM documents;"
```

### Check Volumes
```bash
docker volume ls | grep ndatool
```

### Check Volume Data Location
```bash
docker volume inspect ndatool_postgres_data
```

## Backup Recommendations

### Backup Database
```bash
docker exec nda-postgres pg_dump -U nda_user nda_db > backup_$(date +%Y%m%d).sql
```

### Backup Volumes
```bash
# Backup all volumes
docker run --rm -v ndatool_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data
docker run --rm -v ndatool_minio_data:/data -v $(pwd):/backup alpine tar czf /backup/minio_backup.tar.gz /data
```

## Restore from Backup

### Restore Database
```bash
docker exec -i nda-postgres psql -U nda_user nda_db < backup_YYYYMMDD.sql
```

## Troubleshooting

### If Data Appears Lost After Restart

1. **Check if volumes exist:**
   ```bash
   docker volume ls | grep ndatool
   ```

2. **Check container logs:**
   ```bash
   docker compose logs api
   docker compose logs postgres
   ```

3. **Verify volumes are mounted:**
   ```bash
   docker inspect nda-postgres | grep -A 10 Mounts
   ```

4. **Check database connection:**
   ```bash
   docker exec nda-postgres psql -U nda_user -d nda_db -c "\dt"
   ```

## Best Practices

1. **Always use `docker compose restart`** instead of `down` + `up` for quick restarts
2. **Use `docker compose up -d --force-recreate`** when you need to apply new environment variables
3. **Never use `-v` flag** with `docker compose down` unless you want to delete all data
4. **Create backups** before major changes or updates
5. **Use version control** for configuration files (docker-compose.yml, .env.example)

## Current Data Status

To check your current data:
```bash
# Count documents
docker exec nda-api python3 -c "
from api.db import get_db_session
from api.db.schema import Document
db = get_db_session()
print(f'Documents: {db.query(Document).count()}')
db.close()
"
```
