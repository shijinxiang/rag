"""
=============================================================================
Query Service — End-to-end Q&A orchestration (Phase 2 upgraded)
=============================================================================

Pipeline when all features are enabled:

    Query Rewrite → Multi-Query → Hybrid Retrieve → Rerank → Generate
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from langchain_core.documents import Document as LCDocument
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.rag.reranker import Reranker
from app.rag.query_rewriter import QueryRewriter
from app.rag.retriever import Retriever
from app.services.generation_service import (
    ContextDoc,
    GenerationResult,
    GenerationService,
)

logger = logging.getLogger(__name__)


class QueryService:
    """Orchestrates the full Q&A pipeline: rewrite → retrieve → rerank → generate."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._retriever = Retriever()
        self._generator = GenerationService()

        # Phase 2 components are lazily created on first use
        self._rewriter: Optional[QueryRewriter] = None
        self._reranker: Optional[Reranker] = None

    # ------------------------------------------------------------------
    # Lazy initializers
    # ------------------------------------------------------------------

    def _get_rewriter(self) -> QueryRewriter:
        if self._rewriter is None:
            self._rewriter = QueryRewriter()
        return self._rewriter

    def _get_reranker(self) -> Reranker:
        if self._reranker is None:
            self._reranker = Reranker()
        return self._reranker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ask(
        self,
        question: str,
        user_id: Optional[str] = None,
        filters: Optional[dict] = None,
        top_k: Optional[int] = None,
        stream: bool = False,
    ) -> "QueryResult":
        """Execute a Q&A query through the full Phase 2 pipeline.

        Args:
            question: User's natural language question.
            user_id:  Optional user ID for logging.
            filters:  Optional metadata filters for retrieval (RBAC).
            top_k:    Number of documents to retrieve.
            stream:   If True, return SSE stream instead of full answer.

        Returns:
            QueryResult with answer, sources, and metadata.
        """
        k = top_k or settings.RAG_TOP_K

        # ---- Step 0: Query Rewrite (Phase 2) ----
        rewritten_query = question
        if settings.RAG_QUERY_REWRITE_ENABLED:
            try:
                rewritten_query = await self._get_rewriter().rewrite(question)
                logger.debug("Rewritten query: '%s' → '%s'", question, rewritten_query)
            except Exception:
                logger.warning("Query rewrite failed — using original question.")
                rewritten_query = question

        # ---- Step 0b: Multi-Query (Phase 2) ----
        if settings.RAG_MULTI_QUERY_ENABLED:
            try:
                sub_queries = await self._get_rewriter().multi_query(
                    rewritten_query
                )
                docs_with_scores = await self._multi_query_retrieve(
                    sub_queries, k, filters
                )
            except Exception:
                logger.warning("Multi-query failed — falling back to single query.")
                docs_with_scores = self._do_retrieve(rewritten_query, k, filters)
        else:
            docs_with_scores = self._do_retrieve(rewritten_query, k, filters)

        # ---- Step 2: Rerank (Phase 2) ----
        if settings.RAG_RERANKER_ENABLED and docs_with_scores:
            try:
                docs = [doc for doc, _score in docs_with_scores]
                docs_with_scores = await self._get_reranker().rerank(
                    rewritten_query,
                    docs,
                    top_k=settings.RAG_RERANK_TOP_K,
                )
            except Exception:
                logger.warning("Reranking failed — using original retrieval order.")

        # ---- Step 3: Convert to ContextDoc ----
        contexts = []
        for doc, score in docs_with_scores:
            ctx = ContextDoc(
                content=doc.page_content,
                doc_title=doc.metadata.get("doc_title", "Unknown"),
                doc_id=doc.metadata.get("doc_id", ""),
                chunk_id=doc.metadata.get("chunk_id", ""),
                page_number=doc.metadata.get("page"),
                score=round(score, 4),
                metadata=doc.metadata,
            )
            contexts.append(ctx)

        # ---- Step 4: Generate ----
        gen_result = await self._generator.generate(
            question=question,
            contexts=contexts,
            temperature=0.3,
            stream=stream,
        )

        # ---- Step 5: Build result ----
        result = QueryResult(
            query_id=str(uuid.uuid4()),
            question=question,
            answer=gen_result.answer,
            sources=gen_result.citations,
            stream=gen_result.stream,
            retrieval_count=len(contexts),
            prompt_tokens=gen_result.prompt_tokens,
            completion_tokens=gen_result.completion_tokens,
            total_tokens=gen_result.total_tokens,
        )

        logger.info(
            "Query '%s': retrieved %d docs, answer %d chars, %d tokens%s%s%s",
            question[:50],
            len(contexts),
            len(gen_result.answer),
            gen_result.total_tokens,
            " [hybrid]" if settings.RAG_HYBRID_SEARCH_ENABLED else "",
            " [reranked]" if settings.RAG_RERANKER_ENABLED else "",
            " [rewritten]" if settings.RAG_QUERY_REWRITE_ENABLED else "",
        )

        return result

    async def retrieve_only(
        self,
        question: str,
        filters: Optional[dict] = None,
        top_k: Optional[int] = None,
    ) -> list[dict]:
        """Retrieve relevant documents without generating an answer.

        Runs the same rewrite → retrieve → rerank pipeline as ``ask()``
        but stops before LLM generation.
        """
        k = top_k or settings.RAG_TOP_K

        # ---- Query Rewrite ----
        rewritten_query = question
        if settings.RAG_QUERY_REWRITE_ENABLED:
            try:
                rewritten_query = await self._get_rewriter().rewrite(question)
            except Exception:
                rewritten_query = question

        # ---- Multi-Query or single retrieval ----
        if settings.RAG_MULTI_QUERY_ENABLED:
            try:
                sub_queries = await self._get_rewriter().multi_query(
                    rewritten_query
                )
                docs_with_scores = await self._multi_query_retrieve(
                    sub_queries, k, filters
                )
            except Exception:
                docs_with_scores = self._do_retrieve(rewritten_query, k, filters)
        else:
            docs_with_scores = self._do_retrieve(rewritten_query, k, filters)

        # ---- Rerank ----
        if settings.RAG_RERANKER_ENABLED and docs_with_scores:
            try:
                docs = [doc for doc, _score in docs_with_scores]
                docs_with_scores = await self._get_reranker().rerank(
                    rewritten_query,
                    docs,
                    top_k=settings.RAG_RERANK_TOP_K,
                )
            except Exception:
                pass

        return [
            {
                "content": doc.page_content,
                "doc_title": doc.metadata.get("doc_title", "Unknown"),
                "doc_id": doc.metadata.get("doc_id", ""),
                "page_number": doc.metadata.get("page"),
                "score": round(score, 4),
            }
            for doc, score in docs_with_scores
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _do_retrieve(
        self,
        query: str,
        k: int,
        filters: dict | None,
    ) -> list[tuple[LCDocument, float]]:
        """Single-query retrieval with graceful degradation."""
        try:
            return self._retriever.retrieve_with_scores(
                query=query, top_k=k, filters=filters
            )
        except Exception:
            logger.warning(
                "Vector retrieval unavailable — returning empty context."
            )
            return []

    async def _multi_query_retrieve(
        self,
        sub_queries: list[str],
        k: int,
        filters: dict | None,
    ) -> list[tuple[LCDocument, float]]:
        """Retrieve for each sub-query, merge, and deduplicate."""
        all_results: list[tuple[LCDocument, float]] = []
        seen: set[str] = set()

        for sq in sub_queries:
            results = self._do_retrieve(sq, k, filters)
            for doc, score in results:
                key = self._doc_key(doc)
                if key not in seen:
                    seen.add(key)
                    all_results.append((doc, score))

        # Sort by score descending
        all_results.sort(key=lambda x: x[1], reverse=True)
        return all_results[:k]

    @staticmethod
    def _doc_key(doc: LCDocument) -> str:
        """Build a deduplication key from document metadata."""
        meta = doc.metadata or {}
        chunk_id = meta.get("chunk_id")
        if chunk_id:
            return str(chunk_id)
        doc_id = meta.get("doc_id", "unknown")
        chunk_index = meta.get("chunk_index", "0")
        return f"{doc_id}:{chunk_index}"


class QueryResult:
    """Result of a Q&A query."""

    def __init__(
        self,
        query_id: str,
        question: str,
        answer: str,
        sources: list[dict],
        stream=None,
        retrieval_count: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ):
        self.query_id = query_id
        self.question = question
        self.answer = answer
        self.sources = sources
        self.stream = stream
        self.retrieval_count = retrieval_count
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
