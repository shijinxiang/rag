"""
=============================================================================
Agent Nodes — LangGraph node functions for the RAG agent
=============================================================================

Each node is either an ``async`` function that receives the full
``AgentState`` and returns a dict of state updates, or a synchronous
function for conditional routing.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from openai import AsyncOpenAI

from app.config import settings
from app.rag.retriever import Retriever
from app.rag.query_rewriter import QueryRewriter
from app.services.generation_service import ContextDoc, GenerationService
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CLASSIFY_PROMPT = """You are a query classifier for an enterprise knowledge base.
Classify the user's question into ONE of these categories:

- **retrieval_qa**: The user is asking about company policies, HR rules, finance
  guidelines, API documentation, product manuals, or any factual information
  that would be in the knowledge base.  MOST questions fall here.
- **general_chat**: The user is greeting, asking about the assistant itself,
  or making small talk.  No need to search the knowledge base.
- **document_operation**: The user wants to upload, delete, list, or manage
  documents (e.g. "帮我上传一份文件", "删除文档", "有哪些文档").

Respond with ONLY the category name, nothing else."""

# ---------------------------------------------------------------------------
# Services (lazy initialised)
# ---------------------------------------------------------------------------

_llm_client: AsyncOpenAI | None = None
_rewriter: QueryRewriter | None = None
_generator: GenerationService | None = None
_retriever: Retriever | None = None


def _get_llm() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            max_retries=2,
            timeout=30.0,
        )
    return _llm_client


def _get_rewriter() -> QueryRewriter:
    global _rewriter
    if _rewriter is None:
        _rewriter = QueryRewriter(client=_get_llm())
    return _rewriter


def _get_generator() -> GenerationService:
    global _generator
    if _generator is None:
        _generator = GenerationService(client=_get_llm())
    return _generator


def _get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def classify_node(state: AgentState) -> dict[str, Any]:
    """Classify the user's question into an intent category.

    Uses a fast LLM call (gpt-4o-mini) with a strict classification prompt.
    Falls back to ``retrieval_qa`` on any error.
    """
    question = state.get("question", "")
    if not question.strip():
        return {"classification": "general_chat"}

    try:
        response = await _get_llm().chat.completions.create(
            model=settings.RAG_QUERY_REWRITE_MODEL,
            messages=[
                {"role": "system", "content": _CLASSIFY_PROMPT},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
            max_tokens=20,
        )
        cls = (response.choices[0].message.content or "").strip().lower()
        if cls not in ("retrieval_qa", "general_chat", "document_operation"):
            cls = "retrieval_qa"
        logger.debug("Classified question '%s' as '%s'", question[:50], cls)
        return {"classification": cls}
    except Exception:
        logger.warning("Classification failed — defaulting to retrieval_qa.")
        return {"classification": "retrieval_qa"}


async def retrieve_node(state: AgentState) -> dict[str, Any]:
    """Run the hybrid retrieval pipeline (Phase 2).

    Rewrites the query, performs hybrid search, and prepares the context
    for generation.
    """
    question = state.get("question", "")
    top_k = state.get("top_k", settings.RAG_TOP_K)
    filters = state.get("filters")

    # ---- Query rewrite ----
    rewritten = question
    if settings.RAG_QUERY_REWRITE_ENABLED:
        try:
            rewritten = await _get_rewriter().rewrite(question)
        except Exception:
            logger.warning("Rewrite failed in agent — using original query.")

    # ---- Retrieve ----
    try:
        docs_with_scores = _get_retriever().retrieve_with_scores(
            query=rewritten,
            top_k=top_k,
            filters=filters,
        )
    except Exception:
        logger.warning("Retrieval failed in agent — returning empty context.")
        docs_with_scores = []

    # ---- Rerank ----
    if settings.RAG_RERANKER_ENABLED and docs_with_scores:
        try:
            from app.rag.reranker import Reranker

            reranker = Reranker()
            docs = [doc for doc, _score in docs_with_scores]
            docs_with_scores = await reranker.rerank(
                rewritten, docs, top_k=settings.RAG_RERANK_TOP_K
            )
        except Exception:
            logger.warning("Rerank failed in agent — using original order.")

    # ---- Serialise docs ----
    serialised = [
        {
            "content": doc.page_content,
            "doc_title": doc.metadata.get("doc_title", "Unknown"),
            "doc_id": doc.metadata.get("doc_id", ""),
            "chunk_id": doc.metadata.get("chunk_id", ""),
            "page_number": doc.metadata.get("page"),
            "score": round(score, 4),
        }
        for doc, score in docs_with_scores
    ]

    return {
        "rewritten_query": rewritten,
        "retrieved_docs": serialised,
    }


async def generate_node(state: AgentState) -> dict[str, Any]:
    """Generate an answer using the LLM.

    If ``retrieved_docs`` are available, they are used as context.
    Otherwise answers directly (general_chat fallback).
    """
    question = state.get("question", "")
    docs = state.get("retrieved_docs", [])

    if docs:
        # Build ContextDoc list for the generation service
        contexts = [
            ContextDoc(
                content=d["content"],
                doc_title=d.get("doc_title", "Unknown"),
                doc_id=d.get("doc_id", ""),
                chunk_id=d.get("chunk_id", ""),
                page_number=d.get("page_number"),
                score=d.get("score", 0.0),
            )
            for d in docs
        ]
        result = await _get_generator().generate(
            question=question,
            contexts=contexts,
            temperature=0.3,
            stream=False,
        )
        return {
            "answer": result.answer,
            "citations": result.citations,
        }
    else:
        # No context — direct LLM answer (general chat)
        response = await _get_llm().chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个企业知识库助手。当前没有检索到相关文档，"
                        "请如实告知用户无法从知识库中找到相关信息。"
                        "如果是日常对话，可以简短回应。"
                    ),
                },
                {"role": "user", "content": question},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        answer = response.choices[0].message.content or ""
        return {
            "answer": answer,
            "citations": [],
        }


async def review_node(state: AgentState) -> dict[str, Any]:
    """Human-in-the-loop review node.

    Currently this is a pass-through that logs the need for review.
    In production, this would interrupt the graph and wait for a human
    to approve or reject via the API.
    """
    question = state.get("question", "")
    classification = state.get("classification", "")

    if state.get("needs_review"):
        logger.info(
            "Agent action requires review: question='%s', class='%s'",
            question[:50],
            classification,
        )
        # In production: raise an interrupt / suspend here
        # For now, auto-approve
        return {"review_approved": True}

    return {"review_approved": True}


# ---------------------------------------------------------------------------
# Conditional routing functions
# ---------------------------------------------------------------------------


def route_after_classify(state: AgentState) -> str:
    """Route to the next node based on intent classification."""
    cls = state.get("classification", "retrieval_qa")

    if cls == "retrieval_qa":
        return "retrieve"
    elif cls == "document_operation":
        return "review"
    else:
        # general_chat → generate directly (no retrieval)
        return "generate"


def route_after_retrieve(state: AgentState) -> str:
    """After retrieval, always generate."""
    return "generate"


def route_after_review(state: AgentState) -> str:
    """After review, generate or end."""
    if state.get("review_approved"):
        return "generate"
    return "__end__"