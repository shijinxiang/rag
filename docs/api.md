# API Design Overview

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
All application endpoints except `/health`, `/auth/login`, `/auth/register`, and
`/auth/refresh` require a Bearer JWT token. Refresh accepts a refresh token in
the JSON request body:
```
Authorization: Bearer <access_token>
```

## Endpoint Summary

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Application status/version/environment |

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login, returns access + refresh tokens |
| POST | `/auth/refresh` | Refresh access token |
| GET | `/auth/me` | Current database user and role |

Registration creates an employee. Roles are assigned using the trusted
`python -m app.manage_user` CLI. Access tokens expire after 30 minutes and
refresh tokens after 7 days by default. Invalid/expired tokens return 401;
authenticated users without permission receive 403. Logout clears browser
tokens; refresh tokens are stateless, and deactivated users cannot refresh.

### Documents
| Method | Path | Description |
|---|---|---|
| POST | `/documents/upload` | Upload document (PDF/MD/TXT/DOCX) |
| GET | `/documents` | List documents (with filters) |
| GET | `/documents/{id}` | Document metadata, processing status, failure details |
| GET | `/documents/{id}/chunks` | Document chunks |
| DELETE | `/documents/{id}` | Delete document + chunks + embeddings |
| POST | `/documents/{id}/retry` | Retry a failed document (202) |
| POST | `/documents/{id}/review` | Request deletion review (202) |

Upload returns 201 with `pending` status. Managers can upload/retry/delete only
within their department; administrators can manage all departments. Employees
can read and request review for documents within their department. Department
is enforced for queries regardless of a client-supplied filter.

### Queries (Q&A)
| Method | Path | Description |
|---|---|---|
| POST | `/queries` | Submit a question (returns answer + sources) |
| POST | `/queries/stream` | Submit a question (SSE streaming) |
| POST | `/queries/retrieve` | Retrieval-only response |
| POST | `/queries/agent` | LangGraph agent response |

### Admin
| Method | Path | Description |
|---|---|---|
| GET | `/admin/audit-logs` | Audit log list |
| GET | `/admin/reviews` | Persistent review requests (default pending) |
| POST | `/admin/reviews/{id}/approve` | Approve and execute deletion |
| POST | `/admin/reviews/{id}/reject` | Reject request |

Administrator role is required. Repeated decisions return 409. Both decision
endpoints accept `{"note": "optional reason"}`. Evaluation runs from
`scripts/run_evaluation.py`; `/metrics` exposes Prometheus metrics.

## Response Format

### Success
```json
{"status": "healthy", "version": "1.0.0", "environment": "development"}
```

### Error
```json
{"detail": "Document not found"}
```

Unhandled failures return the structured `error` envelope with
`code: INTERNAL_ERROR`; expected API errors use FastAPI's `detail` field.

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
event: sources
data: [{"doc_id": "...", "chunk_id": "...", "score": 0.92}]

event: token
data: 根据

event: token
data: 公司

event: done
data: {"query_id": "...", "retrieval_count": 1}
```
