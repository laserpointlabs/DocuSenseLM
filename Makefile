.PHONY: help setup up down logs clean seed reindex eval

help:
	@echo "Available commands:"
	@echo "  make setup      - Initial setup (copy .env, init DB)"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo "  make logs       - Show logs"
	@echo "  make clean      - Clean volumes and containers"
	@echo "  make seed       - Seed sample documents"
	@echo "  make reindex    - Re-index all documents"
	@echo "  make eval       - Run evaluation harness"

setup:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	@echo "✓ Created .env file"
	@docker-compose up -d postgres
	@sleep 5
	@docker-compose exec -T api python api/db/migrations/001_init_schema.py || echo "Waiting for services..."
	@echo "✓ Database initialized"

up:
	docker-compose up -d
	@echo "✓ Services started"
	@echo "  UI: http://localhost:3000"
	@echo "  API: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	@echo "✓ Volumes cleaned"

seed:
	docker-compose exec api python scripts/seed_data.py

reindex:
	docker-compose exec api python scripts/reindex.py --all

eval:
	docker-compose exec api python eval/run_eval.py --verbose
