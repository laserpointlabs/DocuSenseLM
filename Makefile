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
	@echo "  make load-questions - Load competency questions from QA pairs"
	@echo "  make test-questions - Run tests for loaded questions"
	@echo "  make load-and-test - Load questions and run tests"

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

load-questions:
	@echo "Loading competency questions from eval/qa_pairs.json..."
	@python3 scripts/load_competency_questions.py --use-db

test-questions:
	@echo "Running tests for competency questions..."
	@python3 scripts/load_competency_questions.py --test-only --test

load-and-test:
	@echo "Loading questions and running tests..."
	@python3 scripts/load_competency_questions.py --use-db --test

refresh-questions:
	@echo "Refreshing questions (delete old, generate new from documents)..."
	@bash scripts/refresh_questions.sh

clean-questions:
	@echo "Cleaning all competency questions..."
	@python3 scripts/clean_questions.py

generate-doc-questions:
	@echo "Generating document-specific questions..."
	@python3 scripts/generate_document_questions.py --create --no-llm

generate-questions-with-answers:
	@echo "Generating questions with expected answers from documents..."
	@docker-compose exec api python3 /app/scripts/generate_sample_questions.py

review-and-test:
	@echo "Reviewing and testing all competency questions..."
	@docker-compose exec api python /app/scripts/review_and_test_questions.py || docker-compose exec api bash -c "cd /app && python scripts/review_and_test_questions.py"

recalculate-expirations:
	@echo "Recalculating expiration dates from filenames..."
	@python3 scripts/recalculate_expirations.py
