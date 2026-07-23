.PHONY: dev-backend seed test lint up down logs

dev-backend:            ## Run API locally on :8000 (SQLite)
	cd backend && uvicorn app.main:app --reload --port 8000

seed:                   ## Create roles/admin/benchmark (+ demo book if SEED_DEMO_DATA=true)
	cd backend && python -m app.db.seed

test:                   ## Backend test suite
	cd backend && pytest -q

lint:                   ## Ruff lint
	cd backend && ruff check app tests

up:                     ## Full stack via docker compose (frontend :8080, api :8000)
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f backend
