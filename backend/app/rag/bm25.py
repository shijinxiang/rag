"""
=============================================================================
BM25 Sparse Searcher — PostgreSQL full-text + pg_trgm keyword retrieval
=============================================================================

Provides a BM25-style sparse / keyword search over the PGVector-internal
``langchain_pg_embedding`` table using PostgreSQL's built-in full-text
search (``tsvector`` / ``tsquery``) and trigram fuzzy matching (``pg_trgm``).

Because PostgreSQL has no built-in Chinese tokeniser we use the ``simple``
text-search configuration (no stemming, no stop-word list) together with
``pg_trgm`` similarity for trigram-level overlap on unsegmented CJK text.

The final score is a weighted combination:

    score = 0.6 × ts_rank_normalised + 0.4 × similarity_normalised
"""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.documents import Document as LCDocument

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring weights (ts_rank : pg_trgm similarity)
# ---------------------------------------------------------------------------
_TS_RANK_WEIGHT = 0.6
_TRIGRAM_WEIGHT = 0.4
_TRIGRAM_CUTOFF = 0.05  # minimum similarity threshold


class BM25Searcher:
    """Sparse / keyword retriever backed by PostgreSQL full-text search.

    The searcher is **lazy** — no connection is opened until ``search()``
    is called, so constructing one is cheap even when the database isn't
    PostgreSQL (e.g. SQLite in tests).  On non-PostgreSQL databases
    ``search()`` logs a warning and returns an empty list.
    """

    def __init__(
        self,
        connection_string: str | None = None,
        collection_name: str = "rag_documents",
    ):
        self._connection_string = connection_string or settings.DATABASE_URL_SYNC
        self._collection_name = collection_name
        self._engine = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[tuple[LCDocument, float]]:
        """Execute a sparse / keyword search.

        Args:
            query:   Raw user query string.
            top_k:   Max number of results to return (default 20).
            filters: Optional metadata filter dict, e.g.
                     ``{"department": "hr"}``.

        Returns:
            List of ``(LCDocument, relevance_score)`` tuples, or an empty
            list on error or unsupported backend.
        """
        try:
            return self._search_impl(query, top_k=top_k, filters=filters)
        except Exception:
            logger.warning(
                "BM25 search failed — falling back to empty sparse results.",
                exc_info=True,
            )
            return []

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _search_impl(
        self,
        query: str,
        top_k: int,
        filters: dict | None,
    ) -> list[tuple[LCDocument, float]]:
        import sqlalchemy as sa
        from sqlalchemy import text

        # -- Lazy engine creation -------------------------------------------
        if self._engine is None:
            conn_url = (self._connection_string or "").strip()
            if not conn_url or conn_url.startswith("sqlite"):
                logger.info(
                    "BM25Searcher: SQLite backend detected — sparse search "
                    "is unavailable; returning empty results."
                )
                return []
            self._engine = sa.create_engine(conn_url, pool_pre_ping=True)

        # -- Build WHERE clause --------------------------------------------
        where_clauses = [
            """
            (
                to_tsvector('simple', e.document)
                @@ plainto_tsquery('simple', :query)
                OR similarity(e.document, :query) > :trigram_cutoff
            )
            """
        ]
        params: dict = {
            "query": query,
            "trigram_cutoff": _TRIGRAM_CUTOFF,
            "top_k": top_k,
            "collection_name": self._collection_name,
        }

        if filters:
            for key, value in filters.items():
                param_name = f"filter_{key}"
                where_clauses.append(
                    f"e.cmetadata->>'{key}' = :{param_name}"
                )
                params[param_name] = value

        where_sql = " AND ".join(where_clauses)

        # -- Scoring expression -------------------------------------------
        # ts_rank:  normalises to [0, 1] so the weighted combination is
        #           well-behaved.
        # pg_trgm similarity: already in [0, 1].
        sql = f"""
            SELECT
                e.document,
                e.cmetadata,
                (
                    {_TS_RANK_WEIGHT} * ts_rank(
                        to_tsvector('simple', e.document),
                        plainto_tsquery('simple', :query),
                        32  -- normalise divisor (0=no normalisation, 32=norm to doc length)
                    )
                    +
                    {_TRIGRAM_WEIGHT} * COALESCE(
                        similarity(e.document, :query), 0.0
                    )
                ) AS hybrid_score
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c
                ON c.uuid = e.collection_id
            WHERE c.name = :collection_name
              AND ({where_sql})
            ORDER BY hybrid_score DESC
            LIMIT :top_k
        """

        with self._engine.connect() as conn:
            result = conn.execute(text(sql), params)
            rows = result.fetchall()

        docs: list[tuple[LCDocument, float]] = []
        for row in rows:
            content = row[0] or ""
            metadata = row[1] or {}
            score = row[2] or 0.0
            doc = LCDocument(page_content=content, metadata=dict(metadata))
            docs.append((doc, round(float(score), 6)))

        return docs
