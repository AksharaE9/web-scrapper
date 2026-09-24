# LeadCore Zero v2 — Backend

Graph-engineered, keyless, local-first lead intelligence scraper.
₹0 running cost. No external API keys required.

## Environment Variables

Configure `.env` in `backend/`:

```bash
# Database connections
DATABASE_URL=postgresql://user:password@localhost:5432/leadcore?sslmode=require
DATABASE_URL_DIRECT=postgresql://user:password@localhost:5432/leadcore?sslmode=require

# Web crawling contact header
CONTACT_EMAIL=crawler@example.com

# Local LLM integration (Ollama)
LLM_ENABLED=false
OLLAMA_URL=http://localhost:11434
RELEVANCE_LLM_MODEL=qwen2.5:3b-instruct

# FastEmbed / ONNX cache directory
FASTEMBED_CACHE_PATH=./data/cache/fastembed
```

## Setup & Running

```bash
# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Run preflight system health check
uv run python scripts/doctor.py

# Start FastAPI dev server
uv run uvicorn app.main:app --reload --port 8000
```

## Running Tests

```bash
uv run pytest tests/ -v
```
