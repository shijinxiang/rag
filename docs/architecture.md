# Architecture: Enterprise Knowledge RAG Agent

## Overview

Enterprise Knowledge RAG Agent 是一个企业级检索增强生成（RAG）智能体系统，支持多格式文档上传、向量化索引、混合检索、重排序、Agent 工具调用、权限控制、自动评估和全链路可观测。

## High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           Client Layer                                   │
│  ┌──────────────────────────┐     ┌──────────────────────────────────┐  │
│  │   Next.js Frontend       │     │   Swagger Docs / API Explorer    │  │
│  │   (React + Tailwind)     │     │   (OpenAPI 3.0)                 │  │
│  └────────────┬─────────────┘     └──────────────────────────────────┘  │
└───────────────┼─────────────────────────────────────────────────────────┘
                │ HTTPS / SSE
┌───────────────┼─────────────────────────────────────────────────────────┐
│               ▼               Gateway Layer                              │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      Nginx Reverse Proxy                          │   │
│  │            (SSL termination, load balancing, caching)             │   │
│  └────────────────────────────┬─────────────────────────────────────┘   │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────┐
│                               ▼          Application Layer               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    FastAPI Backend Server                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────────┐   │   │
│  │  │ Auth     │ │ Admin    │ │ Document   │ │ Query / Chat     │   │   │
│  │  │ JWT+RBAC │ │ APIs     │ │ APIs       │ │ APIs (SSE)       │   │   │
│  │  └──────────┘ └──────────┘ └────────────┘ └──────────────────┘   │   │
│  └────────────────────────────┬─────────────────────────────────────┘   │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────┐
│                               ▼          Agent Layer                     │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      LangGraph Agent                               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────────┐   │   │
│  │  │ Classify │ │ Retrieve │ │ Generate   │ │ Tools: search,   │   │   │
│  │  │ Node     │→│ Node     │→│ Node       │ │ sql, summarize   │   │   │
│  │  └──────────┘ └──────────┘ └────────────┘ └──────────────────┘   │   │
│  │                        ↑ Human-in-the-Loop ↓                       │   │
│  │                    ┌─────────────────────┐                         │   │
│  │                    │  Review Node        │                         │   │
│  │                    │  (approve / reject) │                         │   │
│  │                    └─────────────────────┘                         │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────┐
│                               ▼           RAG Layer                      │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐     │   │
│  │  │ Document │ │ Chunking │ │ Embedding│ │ Retrieval        │     │   │
│  │  │ Loader   │→│ Strategy │→│ Engine   │→│ (Hybrid+Rerank) │     │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────┐
│                               ▼          Data Layer                      │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────────────┐     │
│  │ PostgreSQL  │ │ pgvector    │ │ Redis    │ │ MinIO / S3       │     │
│  │ (metadata)  │ │ (vectors)   │ │ (cache)  │ │ (raw files)      │     │
│  └─────────────┘ └─────────────┘ └──────────┘ └──────────────────┘     │
└──────────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────┐
│                               ▼        Observability Layer               │
│  ┌────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │ LangSmith      │ │ Prometheus   │ │ Grafana      │ │ Ragas        │ │
│  │ (LLM tracing)  │ │ (metrics)    │ │ (dashboards) │ │ (eval)       │ │
│  └────────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack Decisions

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | Next.js 14 + Tailwind | SSR, App Router, strong ecosystem |
| Backend | FastAPI | Async-native, auto OpenAPI, type-safe |
| Agent | LangGraph | Stateful, durable execution, human-in-the-loop |
| RAG | LangChain | Mature retriever/tool integrations |
| LLM | OpenAI Responses API | Latest API, agent-oriented |
| Embedding | text-embedding-3-small | Good quality/cost ratio, dimensions control |
| Vector DB | pgvector → Milvus | Start simple, scale when needed |
| Relational DB | PostgreSQL 16 | Metadata, users, audit logs |
| Cache/Queue | Redis + Celery | Async document processing |
| Storage | MinIO | S3-compatible, self-hosted |
| Auth | JWT + RBAC | Stateless auth with role-based access |
| Observability | LangSmith + Prometheus + Grafana | Full-stack tracing + metrics |
| Evaluation | Ragas | Automated RAG evaluation |
| Deployment | Docker Compose → K8s | Gradual complexity |

## Key Design Decisions

1. **pgvector first, Milvus later**: pgvector co-locates vectors with business data in PostgreSQL, simplifying the MVP and demonstrating enterprise DB integration. Milvus is reserved for when scale demands it.

2. **Hybrid Search**: Dense (semantic) + Sparse (keyword/BM25) + Reranker. Most RAG failures come from poor retrieval, not poor generation.

3. **LangGraph over raw LangChain chains**: Better support for conditional routing, tool calling loops, human-in-the-loop, and state persistence.

4. **Async-first**: All I/O (DB, HTTP, file) is async. Background tasks via Celery for heavy operations like document parsing and embedding.

5. **Evaluation built-in, not afterthought**: Golden Dataset + Ragas metrics from stage 5, but the data model supports it from day one.
