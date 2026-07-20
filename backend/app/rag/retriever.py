"""
=============================================================================
Retriever — RAG retrieval facade with hybrid search support
=============================================================================

Phase 2 upgrade: supports dense (vector) + sparse (BM25) hybrid retrieval
with Reciprocal Rank Fusion when ``RAG_HYBRID_SEARCH_ENABLED`` is set.
"""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.documents import Document as LCDocument

from app.config import settings
from app.db.vector_store import VectorStore, get_vector_store
from app.rag.bm25 import BM25Searcher
from app.rag.fusion import reciprocal_rank_fusion

logger = logging.getLogger(__name__)


class Retriever:
    """RAG retriever with optional hybrid (dense + sparse) search.

    When *hybrid* is enabled the retriever fans out to both the vector
    store (dense / semantic) and a BM25 full-text searcher (sparse /
    keyword), then merges the two ranked lists via Reciprocal Rank Fusion.
    """

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        bm25_searcher: BM25Searcher | None = None,
    ):
        self._store = vector_store or get_vector_store()
        self._bm25 = bm25_searcher

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filters: dict | None = None,
        hybrid: bool | None = None,
    ) -> list[LCDocument]:
        """Retrieve top-k documents (scores discarded)."""
        results = self.retrieve_with_scores(
            query=query, top_k=top_k, filters=filters, hybrid=hybrid
        )
        return [doc for doc, _score in results]

    def retrieve_with_scores(
        self,
        query: str,
        top_k: int | None = None,
        filters: dict | None = None,
        hybrid: bool | None = None,
    ) -> list[tuple[LCDocument, float]]:
        """Retrieve top-k documents with relevance scores.

        Args:
            query:   User query string.
            top_k:   Number of results (default ``RAG_TOP_K``).
            filters: Metadata filter dict for RBAC / department filtering.
            hybrid:  Override ``RAG_HYBRID_SEARCH_ENABLED``; ``None`` means
                     "read from settings".

        Returns:
            ``(document, score)`` tuples sorted by descending relevance.
        """
        k = top_k or settings.RAG_TOP_K
        use_hybrid = hybrid if hybrid is not None else settings.RAG_HYBRID_SEARCH_ENABLED

        # --- Hybrid path ---------------------------------------------------
        if use_hybrid and self._bm25 is not None:
            return self._hybrid_retrieve(query, k=k, filters=filters)

        # --- Dense-only path (existing behaviour) --------------------------
        return self._store.similarity_search_with_score(
            query, k=k, filter=filters
        )

    # ------------------------------------------------------------------
    # Hybrid internals
    # ------------------------------------------------------------------

    def _hybrid_retrieve(
        self,
        query: str,
        k: int,
        filters: dict | None,
    ) -> list[tuple[LCDocument, float]]:
        recall_k = settings.RAG_HYBRID_TOP_K

        try:
            # Fan out to both paths
            dense = self._store.similarity_search_with_score(
                query, k=recall_k, filter=filters
            )
        except Exception:
            logger.warning(
                "Dense retrieval failed in hybrid mode — returning empty."
            )
            return []

        try:
            sparse = self._bm25.search(query, top_k=recall_k, filters=filters)
        except Exception:
            logger.warning(
                "Sparse retrieval failed in hybrid mode — using dense results only."
            )
            return dense[:k]

        # Merge & truncate
        try:
            merged = reciprocal_rank_fusion(dense, sparse, top_k=k)
        except Exception:
            logger.warning(
                "RRF fusion failed — falling back to dense results."
            )
            return dense[:k]

        return merged

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def format_context(documents: list[LCDocument]) -> str:
        """Format retrieved documents into a prompt context string."""
        parts = []
        for i, doc in enumerate(documents, 1):
            title = doc.metadata.get("doc_title", "Unknown")
            page = doc.metadata.get("page", "N/A")
            source = doc.metadata.get("source_file", "Unknown")
            parts.append(
                f"--- [文档 {i}] {title} | 页码: {page} | 来源: {source} ---\n"
                f"{doc.page_content}"
            )
        return "\n\n".join(parts)
