.PHONY: dev migrate seed test lint clean

dev:
	@echo "Starting LeadCore Zero v2..."
	@powershell -Command "Start-Process powershell -ArgumentList 'cd backend; uv run uvicorn app.main:app --reload --port 8000'; Start-Process powershell -ArgumentList 'cd frontend; npm run dev'"

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python scripts/import_seeds.py

test:
	cd backend && uv run pytest tests/ -v

lint:
	cd backend && uv run ruff check .
