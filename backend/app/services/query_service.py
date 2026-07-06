"""
=============================================================================
Query Service — End-to-end Q&A orchestration
=============================================================================
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from langchain_core.documents import Document as LCDocument
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.rag.retriever import Retriever
from app.services.generation_service import (
    ContextDoc,
    GenerationResult,
    GenerationService,
)

logger = logging.getLogger(__name__)


class QueryService:
    """Orchestrates the full Q&A pipeline: retrieve → generate → record."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._retriever = Retriever()
        self._generator = GenerationService()

    async def ask(
        self,
        question: str,
        user_id: Optional[str] = None,
        filters: Optional[dict] = None,
        top_k: Optional[int] = None,
        stream: bool = False,
    ) -> "QueryResult":
        """
        Execute a Q&A query.

        Args:
            question: User's natural language question.
            user_id: Optional user ID for logging.
            filters: Optional metadata filters for retrieval (RBAC).
            top_k: Number of documents to retrieve.
            stream: If True, return SSE stream instead of full answer.

        Returns:
            QueryResult with answer, sources, and metadata.
        """
        k = top_k or settings.RAG_TOP_K

        # ---- Step 1: Retrieve (skip on SQLite — no vector store) ----
        docs_with_scores: list[tuple[LCDocument, float]] = []
        try:
            docs_with_scores = self._retriever.retrieve_with_scores(
                query=question, top_k=k, filters=filters
            )
        except Exception:
            logger.warning("Vector retrieval unavailable — returning empty context.")

        # ---- Step 2: Convert to ContextDoc ----
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

        # ---- Step 3: Generate ----
        gen_result = await self._generator.generate(
            question=question,
            contexts=contexts,
            temperature=0.3,
            stream=stream,
        )

        # ---- Step 4: Build result ----
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
            "Query '%s': retrieved %d docs, answer %d chars, %d tokens",
            question[:50],
            len(contexts),
            len(gen_result.answer),
            gen_result.total_tokens,
        )

        return result

    async def retrieve_only(
        self,
        question: str,
        filters: Optional[dict] = None,
        top_k: Optional[int] = None,
    ) -> list[dict]:
        """Retrieve relevant documents without generating an answer."""
        k = top_k or settings.RAG_TOP_K
        docs_with_scores: list[tuple[LCDocument, float]] = []
        try:
            docs_with_scores = self._retriever.retrieve_with_scores(
                query=question, top_k=k, filters=filters
            )
        except Exception:
            logger.warning("Vector retrieval unavailable in retrieve_only - returning empty results.")

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
