"""
=============================================================================
Agent State — LangGraph state definition for the RAG agent
=============================================================================
"""
from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict):
    """State of the LangGraph agent throughout its lifecycle."""

    # ---- Input ----
    question: str
    """Original user question."""

    user_id: str | None
    """Optional user identifier for RBAC / logging."""

    filters: dict[str, Any] | None
    """Metadata filters for RBAC (department, access_level)."""

    top_k: int
    """Number of documents to retrieve."""

    # ---- Classification ----
    classification: str
    """Intent classification: ``retrieval_qa`` | ``general_chat`` | ``document_operation``."""

    # ---- Retrieval ----
    rewritten_query: str | None
    """Query-rewritten version of the question (Phase 2)."""

    retrieved_docs: list[dict[str, Any]]
    """Serialised retrieved documents with scores and metadata."""

    context: str
    """Formatted context string for the LLM prompt."""

    # ---- Generation ----
    answer: str | None
    """Final generated answer."""

    citations: list[dict[str, Any]]
    """Source citations for the answer."""

    # ---- Human-in-the-loop ----
    needs_review: bool
    """Whether the agent should pause for human review."""

    review_approved: bool
    """Whether the human approved the action."""

    review_status: str
    """Review state: ``not_required``, ``pending``, ``approved``, or ``rejected``."""

    tool_calls: list[dict[str, Any]]
    """Structured tool calls and their results, for auditability."""

    tool_result: str | None
    """Most recent tool result available to the generation node."""

    # ---- Conversation ----
    messages: list[dict[str, Any]]
    """Conversation history (role, content)."""

    # ---- Error ----
    error: str | None
    """Error message if something went wrong."""
