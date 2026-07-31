"""
=============================================================================
Agent Tools — Tools that the LangGraph agent can invoke
=============================================================================

Each tool is a plain async function decorated with ``@tool`` from
``langchain_core.tools``.  The agent graph calls these tools during
the ``tools`` node.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.tools import tool

from app.config import settings
from app.rag.retriever import Retriever

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared retriever instance (lazy)
# ---------------------------------------------------------------------------
_retriever: Retriever | None = None


def _get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
async def search_knowledge(
    query: str,
    top_k: int = 10,
    department: Optional[str] = None,
    hybrid: bool = True,
) -> str:
    """Search the enterprise knowledge base for relevant documents.

    Use this tool when you need factual information from company policies,
    HR rules, API documentation, finance guidelines, or any other internal
    document.

    Args:
        query:    The search query (natural language).
        top_k:    Number of documents to return (default 10).
        department: Optional department filter (e.g. "hr", "finance").
        hybrid:   Whether to use hybrid search (dense + BM25). Default True.

    Returns:
        A formatted string of retrieved document excerpts with metadata.
    """
    filters = {"department": department} if department else None
    retriever = _get_retriever()

    docs = retriever.retrieve(
        query=query,
        top_k=top_k,
        filters=filters,
        hybrid=hybrid,
    )

    if not docs:
        return "知识库中未找到相关文档。"

    parts = []
    for i, doc in enumerate(docs, 1):
        title = doc.metadata.get("doc_title", "Unknown")
        page = doc.metadata.get("page", "N/A")
        excerpt = doc.page_content[:300]
        parts.append(
            f"[{i}] 文档: {title} | 页码: {page}\n{excerpt}"
        )
    return "\n\n".join(parts)


@tool
async def get_document_info(doc_id: str) -> str:
    """Get metadata about a specific document by its ID.

    Args:
        doc_id: The UUID of the document.

    Returns:
        Document metadata as a formatted string.
    """
    from app.db.vector_store import get_vector_store

    store = get_vector_store()
    # Query the vector store for document info
    # For now, return a placeholder — full doc metadata retrieval
    # requires the DB session, which is injected at a higher level.
    return (
        f"Document ID: {doc_id}\n"
        f"查询文档详情需要数据库会话，请通过文档管理 API 查看。"
    )


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS: list = [search_knowledge, get_document_info]
"""Registry of all available tools for the agent."""