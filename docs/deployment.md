# Deployment Guide

## Prerequisites

- Docker >= 24.0
- Docker Compose >= 2.20
- Git

## Quick Start (Local Development)

```bash
# 1. Clone the repository
git clone <repo-url>
cd langchain_RAG_agent

# 2. Copy and configure environment variables
cp .env.example .env
# Edit .env with your API keys and secrets

# 3. Start all services
docker compose -f docker/docker-compose.yml up -d

# 4. Check service health
curl http://localhost:8000/api/v1/health
# Expected: {"status":"healthy","version":"1.0.0","services":{"postgres":"up","redis":"up","minio":"up"}}

# 5. Open the application
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# MinIO Console: http://localhost:9001
```

## Development Setup (with Hot Reload)

```bash
# Start services with dev overrides
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d

# Or, run backend locally for faster iteration:
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Run frontend locally:
cd frontend
npm install
npm run dev
```

## Running Database Migrations

```bash
cd backend

# Generate migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Running Tests

```bash
cd backend
pytest tests/ -v --cov=app --cov-report=html

# Specific test
pytest tests/test_retrieval.py -v
```

## Running Evaluations

```bash
cd backend
python scripts/run_evaluation.py --dataset data/golden_dataset/qa_pairs.json
```

## Production Deployment

### Docker Compose (Single Server)
```bash
# Set APP_ENV=production in .env
docker compose -f docker/docker-compose.yml up -d --build
```

### Kubernetes (via Helm or kubectl)
TBD — k8s manifests coming in a future release.

### Cloud Deployment Options
- **Railway**: Point to the Dockerfile, set env vars
- **Render**: Blueprint with docker-compose
- **AWS ECS**: Use Docker images + RDS for PostgreSQL
- **Aliyun ACK**: Container Service for Kubernetes

## Environment Variables Checklist

Before deploying, ensure these variables are set in `.env`:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | App secret (>= 32 chars) |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `JWT_SECRET_KEY` | Yes | JWT signing key |
| `POSTGRES_PASSWORD` | Yes | Database password |
| `MINIO_SECRET_KEY` | Yes | MinIO secret key |
| `LANGSMITH_API_KEY` | No | LangSmith tracing (recommended) |
| `COHERE_API_KEY` | No | Cohere Rerank (for reranker) |
