"""
=============================================================================
Query Pydantic Schemas
=============================================================================
"""
from typing import Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request body for Q&A queries."""
    question: str = Field(..., min_length=1, max_length=5000, description="用户问题")
    top_k: Optional[int] = Field(default=None, ge=1, le=50, description="检索文档数量")
    department: Optional[str] = Field(default=None, description="按部门过滤")
    stream: bool = Field(default=False, description="是否使用 SSE 流式返回")


class SourceCitation(BaseModel):
    """A single source citation in the answer."""
    index: int
    doc_title: str
    doc_id: str
    chunk_id: str = ""
    page_number: Optional[int] = None
    score: float = 0.0
    excerpt: str = ""


class QueryResponse(BaseModel):
    """Response for a Q&A query."""
    query_id: str
    question: str
    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)
    retrieval_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class QueryHistoryItem(BaseModel):
    """A single item in query history."""
    query_id: str
    question: str
    answer_preview: str = ""
    created_at: str = ""


class RetrieveRequest(BaseModel):
    """Request body for retrieval-only endpoint."""
    question: str = Field(..., min_length=1, max_length=5000)
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    department: Optional[str] = None


class RetrieveResult(BaseModel):
    """A single retrieval result."""
    content: str
    doc_title: str
    doc_id: str
    page_number: Optional[int] = None
    score: float = 0.0


class RetrieveResponse(BaseModel):
    """Response for retrieval-only endpoint."""
    query: str
    results: list[RetrieveResult]
    count: int
