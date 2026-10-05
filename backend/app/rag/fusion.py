"""
=============================================================================
Reciprocal Rank Fusion — Merge dense and sparse retrieval results
=============================================================================

RRF combines ranked lists from multiple retrieval methods into a single
relevance-ranked list without normalisation.  See:

    Cormack, Clarke, Buettcher.  "Reciprocal Rank Fusion outperforms
    Condorcet and individual rank learning methods."  SIGIR 2009.

Formula:
    RRF(d) = Σ 1 / (k + rank_i(d))

where rank_i(d) is the position of document d in the i-th ranked list
(1-indexed), and k is a smoothing constant (default 60).
"""
from __future__ import annotations

import logging

from langchain_core.documents import Document as LCDocument

logger = logging.getLogger(__name__)

# Default smoothing constant from the literature — a document ranked #1
# contributes ~1/61, a document ranked #10 contributes ~1/70.
_DEFAULT_K = 60


def _chunk_key(doc: LCDocument) -> str:
    """Build a stable deduplication key for a retrieved document.

    Prefers the ``chunk_id`` metadata field; falls back to
    ``doc_id:chunk_index`` so the function works both with documents
    that carry explicit chunk IDs *and* with pre-PGVector chunks.
    """
    meta = doc.metadata or {}
    chunk_id = meta.get("chunk_id") or meta.get("chunk_id")
    if chunk_id:
        return str(chunk_id)

    doc_id = meta.get("doc_id", "unknown")
    chunk_index = meta.get("chunk_index", "0")
    return f"{doc_id}:{chunk_index}"


def reciprocal_rank_fusion(
    dense_results: list[tuple[LCDocument, float]],
    sparse_results: list[tuple[LCDocument, float]],
    k: int | None = None,
    top_k: int | None = None,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
) -> list[tuple[LCDocument, float]]:
    """Merge dense and sparse ranked lists via Reciprocal Rank Fusion.

    Args:
        dense_results:  (document, score) tuples from dense / vector retrieval.
        sparse_results: (document, score) tuples from sparse / BM25 retrieval.
        k:              Smoothing constant (default ``_DEFAULT_K``, i.e. 60).
        top_k:          Number of results to return (default: all).
        dense_weight:   Multiplier for the dense rank contribution.
        sparse_weight:  Multiplier for the sparse rank contribution.

    Returns:
        Merged list of ``(document, rrf_score)`` tuples sorted by descending
        RRF score, truncated to ``top_k``.
    """
    k = k if k is not None else _DEFAULT_K

    if not dense_results and not sparse_results:
        return []

    # RRF scores keyed by chunk identity
    rrf_scores: dict[str, float] = {}
    doc_map: dict[str, LCDocument] = {}

    # ---- Dense contribution ----
    for rank, (doc, _score) in enumerate(dense_results, start=1):
        key = _chunk_key(doc)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + dense_weight / (k + rank)
        if key not in doc_map:
            doc_map[key] = doc

    # ---- Sparse contribution ----
    for rank, (doc, _score) in enumerate(sparse_results, start=1):
        key = _chunk_key(doc)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + sparse_weight / (k + rank)
        if key not in doc_map:
            doc_map[key] = doc

    # ---- Sort and truncate ----
    sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)  # type: ignore[arg-type]
    if top_k is not None:
        sorted_keys = sorted_keys[:top_k]

    return [(doc_map[key], round(rrf_scores[key], 6)) for key in sorted_keys]
