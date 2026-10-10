# Enterprise Knowledge RAG Agent

<div align="center">

**企业知识库检索与问答智能体**

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://langchain.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

## Overview

Enterprise Knowledge RAG Agent 是一个企业级 RAG（检索增强生成）智能体系统。它能上传多种格式的企业文档、构建知识库、通过混合检索和 Agent 工具调用回答用户问题，并提供全链路的评估、监控和权限管理。

### Core Capabilities

| 能力 | 描述 |
|---|---|
| 📄 **多格式文档** | PDF, Markdown, TXT, DOCX 上传与解析 |
| 🔍 **混合检索** | Dense (语义) + Sparse (BM25/关键词) + RRF 融合 |
| 🎯 **重排序** | Cohere / BGE / Jina Cross-Encoder 精排 |
| ✏️ **查询重写** | LLM 缩写展开 + 多查询生成 |
| 🤖 **Agent 路由** | 自动判断问题类型，调用工具，多步推理 |
| 🔗 **引用溯源** | 每段答案可追溯到源文档、页码、chunk |
| 🔐 **权限隔离** | JWT + RBAC，按部门/角色过滤可检索文档 |
| 📊 **可观测** | LangSmith Tracing + Prometheus + Grafana |
| ✅ **自动评估** | Golden Dataset + Ragas (Hit Rate, MRR, Faithfulness) |
| 🐳 **一键部署** | Docker Compose，5 分钟启动全套服务 |

## Architecture

```text
┌─────────────────────────┐
│   Next.js Frontend      │  ← React + Tailwind, SSE streaming chat
├─────────────────────────┤
│   Nginx Reverse Proxy   │  ← SSL, load balancing
├─────────────────────────┤
│   FastAPI Backend       │  ← REST API + WebSocket
├─────────────────────────┤
│   LangGraph Agent       │  ← Classify → Retrieve → Generate → Tools
├─────────────────────────┤
│   RAG Pipeline          │  ← Hybrid Search → Rerank → Cite
├─────────────────────────┤
│   PostgreSQL + pgvector  │  ← Metadata + Vector store
│   Redis + Celery         │  ← Async tasks + Cache
│   MinIO / S3            │  ← Document file storage
├─────────────────────────┤
│   LangSmith + Prometheus │  ← Tracing + Metrics
└─────────────────────────┘
```

Full architecture: [docs/architecture.md](docs/architecture.md)

## Quick Start

### Prerequisites
- Docker >= 24.0 & Docker Compose >= 2.20
- OpenAI API key for actual embedding and answer generation; local acceptance can run without one

### Launch

```bash
# 1. Clone
git clone https://github.com/shijinxiang/rag.git --branch master && cd rag

# 2. Configure
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, JWT_SECRET_KEY, SECRET_KEY

# 3. Start all services
docker compose --env-file .env -f docker/docker-compose.yml up -d --build

# 4. Verify
curl http://localhost:8000/api/v1/health
# → {"status":"healthy","version":"1.0.0"}

# 5. Open
open http://localhost:3000        # Frontend
open http://localhost:8000/docs   # Swagger API docs when APP_DEBUG=true
```

## Frontend Workspace

The frontend provides desktop sidebar navigation and a compact mobile navigation
bar. Chat supports Markdown, expandable sources, copying answers, cancellation,
and retry. Documents include current-page search, status filters, pagination,
processing details, and deletion confirmation. Administrators have separate
review/audit and model configuration views. API keys remain password fields and
are cleared after a successful submission; the existing server configuration
endpoint still requires a service restart before credentials take effect.

For isolated browser regression checks, install Playwright outside the project
and have Chrome available. Start the frontend on port 3100:

```powershell
npm --prefix frontend run dev -- --hostname 127.0.0.1 --port 3100
```

In another terminal, run from the repository root and set the external dependency
and output paths to your local installation:

```powershell
$env:PLAYWRIGHT_MODULE='D:\langchain_RAG_agent_env\browser-check\node_modules\playwright'
$env:CHECK_OUTPUT='D:\langchain_RAG_agent_env\ui-check'
node scripts/verify_ui.cjs
```

These checks intercept all API calls, use disposable in-memory fixtures, and need
neither Docker nor an API key. They cover authentication views, chat, document
actions, reviews, configuration forms, role-specific controls, and layouts at
1440, 768, 390, and 320 pixels. They do not verify real backend or model behavior.
Use `FRONTEND_URL` to target a different frontend address.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 18, Tailwind CSS |
| Backend | FastAPI, Python 3.12 |
| Agent | LangGraph, LangChain |
| LLM | OpenAI Chat Completions API (configurable model) |
| Embedding | `text-embedding-3-small` (1536d) |
| Vector DB | PostgreSQL + pgvector (→ Milvus) |
| Sparse Search | PostgreSQL tsvector + pg_trgm (BM25) |
| Reranker | Cohere / BGE / Jina |
| Relational DB | PostgreSQL 16 |
| Cache/Queue | Redis + Celery |
| Storage | MinIO (S3-compatible) |
| Auth | JWT + RBAC |
| Monitoring | Prometheus + Grafana |
| Tracing | LangSmith |
| Evaluation | Ragas |

## Project Structure

```
├── backend/              # FastAPI application
│   ├── app/
│   │   ├── api/v1/       # REST API endpoints
│   │   ├── agent/        # LangGraph agent (state, nodes, tools, graph)
│   │   ├── core/         # Security, permissions, logging
│   │   ├── db/           # Database session, vector store, migrations
│   │   ├── middleware/    # Audit, CORS, rate limiting
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── rag/          # Document loader, splitter, retriever, reranker, fusion, BM25
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # Business logic layer
│   │   └── tasks/        # Celery async tasks
│   ├── data/             # Golden dataset, sample documents
│   └── tests/            # Unit and integration tests
├── frontend/             # Next.js application
│   └── src/
│       ├── app/          # App Router pages
│       ├── components/   # UI components (chat, admin, ui)
│       ├── hooks/        # Custom React hooks
│       ├── lib/          # API client, auth utilities
│       └── types/        # TypeScript type definitions
├── docker/               # Docker Compose, Nginx, Postgres, Prometheus configs
├── docs/                 # Architecture, API, RAG design, deployment docs
└── scripts/              # Dev setup, seed data, evaluation scripts
```

## API Endpoints

See [docs/api.md](docs/api.md) for the full API specification.

### Quick Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/documents/upload` | Upload document |
| `POST` | `/api/v1/queries` | Ask a question |
| `POST` | `/api/v1/queries/stream` | Ask a question (SSE stream) |
| `POST` | `/api/v1/queries/retrieve` | Debug-only retrieval |
| `POST` | `/api/v1/queries/agent` | Ask with LangGraph Agent |

## RAG Evaluation Results

The repository includes a deterministic two-case dataset for offline evaluation.
It checks the evaluation code, not real retrieval or generated-answer quality.
Use a representative dataset and valid API key before claiming production scores.

| Metric | Score | Target |
|---|---|---|
| Hit Rate@10 | — | > 0.85 |
| MRR | — | > 0.70 |
| Recall@10 | — | > 0.90 |
| Faithfulness | — | > 0.85 |
| Answer Relevance | — | > 0.80 |

`python scripts/run_evaluation.py --mode offline` produces Hit Rate/Recall 1.0
and MRR/Precision 0.75 on the bundled sample. `--mode ragas` runs actual
LLM-based Ragas metrics when a suitable dataset and API key are configured.

## Documentation

- [Architecture](docs/architecture.md) — System design & tech decisions
- [API Design](docs/api.md) — Endpoint specification
- [RAG Strategy](docs/rag-design.md) — Retrieval pipeline design
- [Evaluation](docs/evaluation.md) — Metrics & methodology
- [Deployment](docs/deployment.md) — Deployment guide
- [Interview Guide (5 min)](docs/interview-5min.md) — Quick project walkthrough
- [Interview Guide (15 min)](docs/interview-15min.md) — Deep-dive technical explanation

## Implementation Status

### Phase 1: Basic RAG MVP — ✅ completed
The core RAG pipeline is implemented and tested (13 tests, 69% coverage).  We can:
- Upload .txt / .md / .pdf / .docx documents
- Parse, chunk, and generate OpenAI embeddings (text-embedding-3-small)
- Store chunks + vectors in PostgreSQL/pgvector (fallback: file-based SQLite for tests)
- POST /api/v1/queries to retrieve top-K chunks and generate an LLM answer
- SSE /api/v1/queries/stream for streaming answers
- Return source citations per answer (doc title, page number, chunk excerpt, similarity score)
- Frontend chat page (Next.js) renders answers + citation cards

### Phase 2: Retrieval Quality — ✅ completed (31 tests, 66% coverage)
Upgraded retrieval with three quality features:
- **Hybrid Search**: Dense (pgvector cosine) + Sparse (PostgreSQL BM25 with ts_rank + pg_trgm) via RRF fusion
- **Cross-Encoder Reranker**: Cohere Rerank API / BGE local / Jina API — configurable provider
- **LLM Query Rewrite**: Abbreviation expansion + multi-query generation (gpt-4o-mini)
- All features gated by config flags, default disabled, backward-compatible

### Phase 3: LangGraph Agent — ✅ core completed
The agent exposes a tested graph for intent classification, retrieval, generation,
allow-listed read-only tool execution, and explicit review state handling.

### Phase 4: Enterprise Capabilities
JWT registration/login/refresh/profile, database-backed roles, department isolation,
asynchronous Celery document processing with failure details and retry, persistent
deletion reviews, administrator approval/rejection, and audit logging are implemented.
The frontend includes authenticated chat, documents, and administrator views.

### Phase 5: Observability and Evaluation
Prometheus request/query/retrieval/task metrics, a provisioned Grafana dashboard,
optional LangSmith tracing, offline retrieval metrics, and a Ragas evaluation CLI
are implemented. LLM evaluation requires external credentials.

### Phase 6: Deployment
Docker Compose includes migrations and health checks for all nine services. CI
checks lint/tests/build, Compose, Kubernetes resources, and Docker images. CD
builds GHCR images; Kubernetes deployment requires a target cluster and GitHub
environment secrets. See [deployment guide](docs/deployment.md) for commands.

### Acceptance and Remaining Limits
- Backend unit and API tests: 46 passing on Windows and in the Linux container.
- Real PostgreSQL migration and repeated upgrade, Celery failure/retry, offline
  pgvector processing, JWT/RBAC, review approval, audit, and vector deletion pass
  via `scripts/verify_stack.py`.
- Actual OpenAI answer generation and LLM-based Ragas scoring have not been run
  without an API key. Production Kubernetes rollout has not been attempted.
- Frontend production dependency audit is clean. Seven high-severity development
  dependency advisories remain in the Tailwind 3/ESLint glob toolchain.

## Roadmap

- [x] **Phase 0**: Project skeleton, Git init, config files
- [x] **Phase 1**: Basic RAG MVP (upload → embed → retrieve → answer)
- [x] **Phase 2**: Retrieval quality (Hybrid Search + Reranker + Query Rewrite)
- [x] **Phase 3**: Agent core (LangGraph routing + read-only tools + review state)
- [x] **Phase 4**: Enterprise (JWT/RBAC + async tasks + audit logging)
- [x] **Phase 5**: Observability & Evaluation (Prometheus metrics + offline evaluation + Grafana)
- [x] **Phase 6**: Production deployment (Compose, CI/CD, Kubernetes manifests)

## License

MIT — see [LICENSE](LICENSE) for details.
