"""
=============================================================================
Reranker — Cross-encoder re-ranking for retrieval quality
=============================================================================

Re-scores a candidate document set with a cross-encoder model that scores
(query, document) pairs jointly rather than via dot-product of separate
embeddings.  Three providers are supported:

* **cohere**  — Cohere Rerank API (``rerank-v3.5``)
* **bge**     — Local BAAI/bge-reranker-v2-m3 via ``sentence-transformers``
* **jina**    — Jina Reranker API (``jina-reranker-v2-base-multilingual``)

All providers are **lazy-initialised** on first use so the reranker is
cheap to construct even when a model or API key is not available.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from langchain_core.documents import Document as LCDocument

from app.config import settings

logger = logging.getLogger(__name__)

# Models used by each provider
_COHERE_MODEL = "rerank-v3.5"
_BGE_MODEL = "BAAI/bge-reranker-v2-m3"
_JINA_MODEL = "jina-reranker-v2-base-multilingual"
_JINA_API_URL = "https://api.jina.ai/v1/rerank"


class Reranker:
    """Cross-encoder re-ranker dispatching to the configured provider."""

    def __init__(self, provider: str | None = None):
        self._provider = (provider or settings.RAG_RERANKER_PROVIDER).lower()
        self._cohere_client = None
        self._bge_model = None
        self._jina_client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def rerank(
        self,
        query: str,
        documents: list[LCDocument],
        top_k: int | None = None,
    ) -> list[tuple[LCDocument, float]]:
        """Re-rank *documents* against *query* and return the top *top_k*.

        Args:
            query:     User query string.
            documents: Candidate documents from retrieval.
            top_k:     Number of results to return (default: ``RAG_RERANK_TOP_K``).

        Returns:
            ``(document, relevance_score)`` tuples sorted by descending score.
        """
        if not documents:
            return []

        k = top_k if top_k is not None else settings.RAG_RERANK_TOP_K

        try:
            if self._provider == "cohere":
                return await self._rerank_cohere(query, documents, k)
            elif self._provider == "bge":
                return await self._rerank_bge(query, documents, k)
            elif self._provider == "jina":
                return await self._rerank_jina(query, documents, k)
            else:
                logger.warning(
                    "Unknown reranker provider '%s' — returning un-reranked top-%d.",
                    self._provider,
                    k,
                )
                return _truncate(documents, k)
        except Exception:
            logger.warning(
                "Reranker (%s) failed — returning un-reranked top-%d.",
                self._provider,
                k,
                exc_info=True,
            )
            return _truncate(documents, k)

    # ------------------------------------------------------------------
    # Cohere
    # ------------------------------------------------------------------

    async def _rerank_cohere(
        self, query: str, documents: list[LCDocument], top_k: int
    ) -> list[tuple[LCDocument, float]]:
        if self._cohere_client is None:
            import cohere

            api_key = settings.RAG_COHERE_API_KEY
            if not api_key:
                raise ValueError("RAG_COHERE_API_KEY is not set")
            self._cohere_client = cohere.AsyncClient(api_key=api_key)

        response = await self._cohere_client.rerank(
            model=_COHERE_MODEL,
            query=query,
            documents=[doc.page_content for doc in documents],
            top_n=min(top_k, len(documents)),
            return_documents=False,
        )

        return [
            (documents[r.index], round(r.relevance_score, 6))
            for r in response.results
        ]

    # ------------------------------------------------------------------
    # BGE (local sentence-transformers)
    # ------------------------------------------------------------------

    async def _rerank_bge(
        self, query: str, documents: list[LCDocument], top_k: int
    ) -> list[tuple[LCDocument, float]]:
        if self._bge_model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading BGE reranker model '%s' ...", _BGE_MODEL)
            self._bge_model = CrossEncoder(
                _BGE_MODEL,
                max_length=512,
            )

        pairs = [(query, doc.page_content) for doc in documents]
        scores = await asyncio.to_thread(
            self._bge_model.predict, pairs, show_progress_bar=False
        )

        scored = list(zip(documents, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(doc, round(float(score), 6)) for doc, score in scored[:top_k]]

    # ------------------------------------------------------------------
    # Jina
    # ------------------------------------------------------------------

    async def _rerank_jina(
        self, query: str, documents: list[LCDocument], top_k: int
    ) -> list[tuple[LCDocument, float]]:
        api_key = settings.RAG_JINA_API_KEY
        if not api_key:
            raise ValueError("RAG_JINA_API_KEY is not set")

        import httpx

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": _JINA_MODEL,
            "query": query,
            "documents": [doc.page_content for doc in documents],
            "top_n": min(top_k, len(documents)),
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(_JINA_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Build an index → score map from the response
        results = data.get("results", [])
        index_score = {r["index"]: r["relevance_score"] for r in results}

        ranked = [
            (documents[idx], round(index_score[idx], 6))
            for idx in sorted(index_score, key=index_score.get, reverse=True)  # type: ignore[arg-type, return-value]
        ]
        return ranked[:top_k]


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------


def _truncate(
    documents: list[LCDocument], top_k: int
) -> list[tuple[LCDocument, float]]:
    """Return the first *top_k* documents with placeholder scores."""
    return [(doc, 0.0) for doc in documents[:top_k]]
