"""
=============================================================================
Query Rewriter — LLM-based query expansion and multi-query generation
=============================================================================

Uses a fast, cheap LLM (default: ``gpt-4o-mini``) to rewrite user queries
before retrieval:

* **Rewrite**: expand abbreviations, normalise informal phrasing,
  add implied enterprise-knowledge-base context.
* **Multi-query**: generate 2-3 alternative formulations of the query
  from different perspectives — each sub-query is retrieved independently
  and the results are deduplicated.

Both methods are idempotent: on any error they return the original input
unchanged so the pipeline degrades gracefully.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_REWRITE_SYSTEM_PROMPT = """You are a query rewriter for an enterprise knowledge base.
Your task is to rewrite the user's query to improve retrieval quality.

Rewrite rules:
1. Expand abbreviations (e.g. "HR" → "Human Resources / 人力资源")
2. Normalise informal or colloquial phrasing to formal, precise language
3. Add implied context — the knowledge base contains HR policies, finance rules,
   API documentation, and internal company procedures
4. Keep the rewritten query in the SAME language as the original
5. Return ONLY the rewritten query text, nothing else — no explanation, no
   prefix, no quotation marks"""

_MULTI_QUERY_SYSTEM_PROMPT = """You are a query expansion assistant for an enterprise
knowledge base. Generate {n} alternative formulations of the user's query from
different perspectives.

Rules:
1. Each variant should approach the question from a different angle
   (e.g. procedural, policy-based, definitional, operational)
2. Use precise, formal language suitable for a knowledge base search
3. Keep all variants in the SAME language as the original
4. Return the variants as a JSON array of strings ONLY — no explanation, no
   prefix, no markdown code fences

Example format: ["variant 1", "variant 2", "variant 3"]"""


class QueryRewriter:
    """LLM-based query rewriter for retrieval quality improvement."""

    def __init__(self, client: Optional[AsyncOpenAI] = None):
        self._client = client or AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            max_retries=2,
            timeout=15.0,
        )
        self._model = settings.RAG_QUERY_REWRITE_MODEL

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def rewrite(self, query: str) -> str:
        """Rewrite *query* for better retrieval.

        On any error returns *query* unchanged.
        """
        try:
            return await self._rewrite_impl(query)
        except Exception:
            logger.warning(
                "Query rewrite failed — using original query.",
                exc_info=True,
            )
            return query

    async def multi_query(self, query: str, n: int | None = None) -> list[str]:
        """Generate *n* alternative sub-queries from *query*.

        On any error returns ``[query]`` (a single-element list).
        """
        n = n or settings.RAG_MULTI_QUERY_COUNT
        try:
            return await self._multi_query_impl(query, n)
        except Exception:
            logger.warning(
                "Multi-query generation failed — using original query only.",
                exc_info=True,
            )
            return [query]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _rewrite_impl(self, query: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=200,
        )
        rewritten = (response.choices[0].message.content or "").strip()
        if not rewritten:
            logger.info("Query rewrite returned empty — using original.")
            return query
        return rewritten

    async def _multi_query_impl(self, query: str, n: int) -> list[str]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": _MULTI_QUERY_SYSTEM_PROMPT.format(n=n),
                },
                {"role": "user", "content": query},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        raw = (response.choices[0].message.content or "").strip()

        # Try JSON parse; if the model returned markdown fences, strip them
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        try:
            variants = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: treat each non-empty line as a variant
            variants = [line.strip() for line in raw.split("\n") if line.strip()]

        if not variants or not isinstance(variants, list):
            return [query]

        # Ensure we only have strings
        variants = [str(v) for v in variants[:n]]

        logger.info("Generated %d multi-query variants.", len(variants))
        return variants
