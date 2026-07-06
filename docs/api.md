# API Design Overview

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
All endpoints except `/health`, `/auth/login`, `/auth/register` require a Bearer JWT token:
```
Authorization: Bearer <access_token>
```

## Endpoint Summary

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check + component status |

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login, returns access + refresh tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Invalidate refresh token |

### Users
| Method | Path | Description |
|---|---|---|
| GET | `/users/me` | Get current user profile |
| PATCH | `/users/me` | Update current user profile |
| GET | `/users` | List users (admin only) |
| PATCH | `/users/{id}/roles` | Update user roles (admin only) |

### Documents
| Method | Path | Description |
|---|---|---|
| POST | `/documents/upload` | Upload document (PDF/MD/TXT/DOCX) |
| GET | `/documents` | List documents (with filters) |
| GET | `/documents/{id}` | Get document detail + chunks |
| DELETE | `/documents/{id}` | Delete document + chunks + embeddings |
| POST | `/documents/{id}/reindex` | Rebuild index for a document |
| GET | `/documents/{id}/versions` | List document versions |

### Queries (Q&A)
| Method | Path | Description |
|---|---|---|
| POST | `/queries` | Submit a question (returns answer + sources) |
| POST | `/queries/stream` | Submit a question (SSE streaming) |
| GET | `/queries` | List query history |
| GET | `/queries/{id}` | Get query detail + retrieval logs |

### Admin
| Method | Path | Description |
|---|---|---|
| GET | `/admin/stats` | Dashboard statistics |
| GET | `/admin/audit-logs` | Audit log list |
| GET | `/admin/usage` | Token usage & cost report |

### Evaluation
| Method | Path | Description |
|---|---|---|
| POST | `/eval/run` | Run evaluation on Golden Dataset |
| GET | `/eval/results` | List evaluation results |
| GET | `/eval/results/{id}` | Get detailed evaluation result |
| GET | `/eval/dataset` | List Golden Dataset Q&A pairs |
| POST | `/eval/dataset` | Add Q&A pair to Golden Dataset |

### Feedback
| Method | Path | Description |
|---|---|---|
| POST | `/feedback` | Submit feedback (thumbs up/down) on an answer |

## Response Format

### Success
```json
{
  "status": "success",
  "data": { ... }
}
```

### Error
```json
{
  "status": "error",
  "error": {
    "code": "NOT_FOUND",
    "message": "Document not found",
    "details": {}
  }
}
```

## Pagination
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "pages": 8
}
```

## Streaming (SSE)
```
event: token
data: {"text": "根据"}

event: token
data: {"text": "公司"}

event: sources
data: {"sources": [{"doc_id": "...", "chunk_id": "...", "score": 0.92}]}

event: done
data: {}
```
