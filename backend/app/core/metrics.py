"""Prometheus application metrics."""
from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "rag_http_requests_total", "HTTP requests", ["method", "path", "status"]
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "rag_http_request_duration_seconds", "HTTP request duration", ["method", "path"]
)
QUERY_REQUESTS_TOTAL = Counter("rag_queries_total", "RAG queries", ["status"])
RETRIEVAL_DOCUMENTS = Histogram("rag_retrieval_documents", "Retrieved document count")
DOCUMENT_PROCESSING_SECONDS = Histogram(
    "rag_document_processing_seconds", "Document processing duration"
)
TASKS_TOTAL = Counter("rag_tasks_total", "Background tasks", ["task", "status"])
