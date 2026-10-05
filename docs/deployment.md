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
Kubernetes manifests are available under `k8s/`. Apply `namespace.yaml`, `configmap.yaml`, a populated copy of `secret.example.yaml`, then the migration Job and workloads.

The Kubernetes workloads require PostgreSQL with pgvector, Redis, and MinIO
endpoints configured in `rag-secrets` and `rag-config`. Provision these managed
services before deploying. `rag-uploads` requires a storage class that supports
ReadWriteMany because API pods and workers share uploads. No production cluster
is configured on the development machine.

CD builds `rag-agent-backend` and `rag-agent-frontend` in GHCR. Set `KUBE_CONFIG`
and `RAG_SECRETS_YAML` in the selected GitHub environment (`staging` or
`production`). Deployment fails clearly when either value is missing.

## Local Acceptance Without an API Key

From the repository root:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d --build
docker compose --env-file .env -f docker/docker-compose.yml ps
docker compose --env-file .env -f docker/docker-compose.yml exec backend alembic current
docker compose --env-file .env -f docker/docker-compose.yml exec backend alembic upgrade head
python scripts/run_evaluation.py --mode offline
docker compose --env-file .env -f docker/docker-compose.yml exec backend python -m pytest tests/ --no-cov
```

The health checks, registration, login, refresh, role controls, review queue,
audit, Redis, MinIO, and monitoring work without an external API key. Actual
embedding and generated answers require a valid `OPENAI_API_KEY`. The stack
verification script uses deterministic test embeddings only within its own
check process, and verifies real PostgreSQL/pgvector storage and deletion.
The application does not substitute fabricated answers for an API failure.

For local execution the script expects the backend at `127.0.0.1:8000` inside
the backend container. Copy it into that container and execute it there when
using Docker Desktop on Windows:

```bash
docker cp scripts/verify_stack.py rag-backend:/tmp/verify_stack.py
docker compose -f docker/docker-compose.yml exec backend python /tmp/verify_stack.py
```

Provision a trusted administrator from the server terminal (password entry is
hidden), or promote an existing registered account:

```bash
docker compose -f docker/docker-compose.yml exec backend \
  python -m app.manage_user admin --email admin@example.com --role admin
docker compose -f docker/docker-compose.yml exec backend \
  python -m app.manage_user manager --role manager --department hr
```

Public registration creates employees. Employees read their department's
documents and submit deletion review requests. Managers upload, retry and
delete only their department's documents. Administrators manage all
departments and decide reviews. Access tokens expire after 30 minutes and
refresh tokens after 7 days by default; invalid, wrong-type and expired tokens
return 401. Refresh tokens are stateless and user deactivation is checked
against the database. Administrative role changes take effect on subsequent
requests.

The optional browser check requires Playwright installed outside the repository
and a local Chrome installation. On this Windows machine:

```powershell
$env:PLAYWRIGHT_MODULE='D:\langchain_RAG_agent_env\browser-check\node_modules\playwright'
$env:DOCKER_CLI='C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$env:CHECK_OUTPUT='D:\langchain_RAG_agent_env'
node scripts/verify_frontend.cjs
```

The check creates uniquely named temporary accounts/documents and removes them
on exit. It verifies registration/login, token refresh, role controls, manager
upload/retry, administrator views, logout, and desktop/mobile page width.

Next.js 15.5.27 includes the current security fixes. `npm audit --omit=dev`
reports no production advisories; seven high-severity development advisories
remain in Tailwind 3/ESLint dependencies. Do not run `npm audit fix --force`
without validating a Tailwind 4 migration.

Grafana (`http://localhost:3001`) loads the RAG Operations dashboard and a
Prometheus data source automatically. LangSmith is disabled by default; set
`LANGSMITH_ENABLED=true` and a key to enable it. For LLM-based Ragas scoring,
provide a dataset containing questions, answers, retrieved context text and
reference answers, and run `python scripts/run_evaluation.py --mode ragas
--metrics faithfulness,answer_relevance,context_precision,context_recall`.

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
