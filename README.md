# Enterprise Knowledge RAG Agent

<div align="center">

**企业知识库检索与问答智能体**

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://langchain.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

## Overview

Enterprise Knowledge RAG Agent 是一个企业级 RAG（检索增强生成）智能体系统。它能上传多种格式的企业文档、构建知识库、通过混合检索和 Agent 工具调用回答用户问题，并提供全链路的评估、监控和权限管理。

### Core Capabilities

| 能力 | 描述 |
|---|---|
| 📄 **多格式文档** | PDF, Markdown, TXT, DOCX 上传与解析 |
| 🔍 **混合检索** | Dense (语义) + Sparse (关键词) + Reranker |
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
- OpenAI API key

### Launch

```bash
# 1. Clone
git clone <repo-url> && cd langchain_RAG_agent

# 2. Configure
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, JWT_SECRET_KEY, SECRET_KEY

# 3. Start all services
docker compose -f docker/docker-compose.yml up -d

# 4. Verify
curl http://localhost:8000/api/v1/health
# → {"status":"healthy","version":"1.0.0"}

# 5. Open
open http://localhost:3000        # Frontend
open http://localhost:8000/docs   # Swagger API docs
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, Tailwind CSS |
| Backend | FastAPI, Python 3.12 |
| Agent | LangGraph, LangChain |
| LLM | OpenAI Responses API (`gpt-5.5`) |
| Embedding | `text-embedding-3-small` (1536d) |
| Vector DB | PostgreSQL + pgvector (→ Milvus) |
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
│   │   ├── agent/        # LangGraph agent definition
│   │   ├── core/         # Security, permissions, logging
│   │   ├── db/           # Database session, vector store, migrations
│   │   ├── middleware/    # Audit, CORS, rate limiting
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── rag/          # Document loader, splitter, retriever, reranker
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
| `POST` | `/api/v1/auth/register` | Register |
| `POST` | `/api/v1/auth/login` | Login |
| `POST` | `/api/v1/documents/upload` | Upload document |
| `POST` | `/api/v1/queries` | Ask a question |
| `POST` | `/api/v1/queries/stream` | Ask a question (SSE stream) |
| `POST` | `/api/v1/eval/run` | Run evaluation |

## RAG Evaluation Results

The system is evaluated on a Golden Dataset of 50-100 Q&A pairs across 5 categories (HR policy, product docs, FAQ, legal, tech manuals).

| Metric | Score | Target |
|---|---|---|
| Hit Rate@10 | — | > 0.85 |
| MRR | — | > 0.70 |
| Recall@10 | — | > 0.90 |
| Faithfulness | — | > 0.85 |
| Answer Relevance | — | > 0.80 |

*Results will be populated after Stage 5 implementation.*

## Documentation

- [Architecture](docs/architecture.md) — System design & tech decisions
- [API Design](docs/api.md) — Endpoint specification
- [RAG Strategy](docs/rag-design.md) — Retrieval pipeline design
- [Evaluation](docs/evaluation.md) — Metrics & methodology
- [Deployment](docs/deployment.md) — Deployment guide
- [Interview Guide (5 min)](docs/interview-5min.md) — Quick project walkthrough
- [Interview Guide (15 min)](docs/interview-15min.md) — Deep-dive technical explanation

## Implementation Status

### Phase 1: Basic RAG MVP — implemented, verification in progress
The core RAG pipeline is implemented and tested (13 tests, 69% coverage).  We can:
- Upload .txt / .md / .pdf / .docx documents
- Parse, chunk, and generate OpenAI embeddings (text-embedding-3-small)
- Store chunks + vectors in PostgreSQL/pgvector (fallback: file-based SQLite for tests)
- POST /api/v1/queries to retrieve top-K chunks and generate an LLM answer
- SSE /api/v1/queries/stream for streaming answers
- Return source citations per answer (doc title, page number, chunk excerpt, similarity score)
- Frontend chat page (Next.js) renders answers + citation cards

### Currently NOT yet implemented (planned for future phases)
- JWT / RBAC authentication
- Hybrid Search (BM25 + dense)
- Reranker (Cohere / BGE / Jina)
- LangGraph Agent routing & tool calling
- Human-in-the-loop review
- Celery async document processing
- LangSmith / Prometheus / Grafana monitoring
- Ragas automated evaluation
- Docker Compose full-stack deployment (infrastructure configs exist, not yet wired end-to-end)

## Roadmap

- [x] **Phase 0**: Project skeleton, Git init, config files
- [x] **Phase 1**: Basic RAG MVP (upload → embed → retrieve → answer)
- [ ] **Phase 2**: Retrieval quality (Hybrid Search + Reranker + Query Rewrite)
- [ ] **Phase 3**: Agent (LangGraph routing + tool calling + human-in-the-loop)
- [ ] **Phase 4**: Enterprise (JWT/RBAC + async tasks + audit logging)
- [ ] **Phase 5**: Observability & Evaluation (Ragas + LangSmith + Grafana)
- [ ] **Phase 6**: Production deployment (CI/CD + K8s + demo)

## License

MIT — see [LICENSE](LICENSE) for details.
