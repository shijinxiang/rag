"""
=============================================================================
Phase 2 Pipeline Tests — hybrid search, reranker, query rewrite, RRF fusion
=============================================================================

These tests exercise the new Phase 2 components independently and as an
integrated pipeline.  All external dependencies (Cohere, BGE, Jina, OpenAI)
are mocked by the fixtures in ``conftest.py`` so no real API keys are needed.
"""

import pytest
from langchain_core.documents import Document as LCDocument

# ============================================================================
# RRF Fusion (pure function — no mocking needed)
# ============================================================================

class TestRRFFusion:
    """Unit tests for reciprocal_rank_fusion()."""

    @staticmethod
    def _doc(content: str, doc_id: str = "d1", chunk_idx: int = 0) -> "LCDocument":
        from langchain_core.documents import Document as LCDocument
        return LCDocument(
            page_content=content,
            metadata={"doc_id": doc_id, "chunk_index": chunk_idx},
        )

    def test_empty_inputs(self):
        from app.rag.fusion import reciprocal_rank_fusion
        result = reciprocal_rank_fusion([], [])
        assert result == []

    def test_dense_only(self):
        """When sparse is empty, dense results pass through (with RRF scores)."""
        from app.rag.fusion import reciprocal_rank_fusion
        d1 = self._doc("doc one", chunk_idx=0)
        d2 = self._doc("doc two", chunk_idx=1)
        dense = [(d1, 0.9), (d2, 0.8)]

        result = reciprocal_rank_fusion(dense, [])
        assert len(result) == 2
        assert result[0][0].page_content == "doc one"
        assert result[1][0].page_content == "doc two"

    def test_sparse_only(self):
        """When dense is empty, sparse results pass through."""
        from app.rag.fusion import reciprocal_rank_fusion
        d1 = self._doc("sparse one", chunk_idx=0)
        sparse = [(d1, 5.0)]

        result = reciprocal_rank_fusion([], sparse)
        assert len(result) == 1
        assert result[0][0].page_content == "sparse one"

    def test_overlap_boosts_rank(self):
        """A document appearing in both lists should rank higher."""
        from app.rag.fusion import reciprocal_rank_fusion
        shared = self._doc("shared", chunk_idx=0)
        dense_only = self._doc("dense only", chunk_idx=1)
        sparse_only = self._doc("sparse only", chunk_idx=2)

        dense = [(shared, 0.9), (dense_only, 0.8)]
        sparse = [(shared, 5.0), (sparse_only, 3.0)]

        result = reciprocal_rank_fusion(dense, sparse)
        # shared should be #1 because it appears in both lists
        assert result[0][0].page_content == "shared"

    def test_top_k_truncation(self):
        from app.rag.fusion import reciprocal_rank_fusion
        docs = [(self._doc(f"doc {i}", chunk_idx=i), 1.0 / (i + 1)) for i in range(10)]
        result = reciprocal_rank_fusion(docs, [], top_k=3)
        assert len(result) == 3

    def test_custom_k(self):
        """Smaller k reduces the smoothing effect."""
        from app.rag.fusion import reciprocal_rank_fusion
        d1 = self._doc("rank1", chunk_idx=0)
        d2 = self._doc("rank2", chunk_idx=1)
        dense = [(d1, 0.9), (d2, 0.8)]

        result_k60 = reciprocal_rank_fusion(dense, [], k=60)
        result_k5 = reciprocal_rank_fusion(dense, [], k=5)
        # Different k values produce different score ratios
        assert result_k60[0][1] != result_k5[0][1]


# ============================================================================
# Query Rewriter (with mocked AsyncOpenAI)
# ============================================================================

class TestQueryRewriter:
    """Tests for the LLM-based query rewriter."""

    @pytest.mark.asyncio
    async def test_rewrite_returns_string(self, _mock_openai):
        """With the global mock the rewriter should return the mock's answer."""
        from app.rag.query_rewriter import QueryRewriter
        rewriter = QueryRewriter()
        result = await rewriter.rewrite("年假怎么请?")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_rewrite_handles_empty_response(self, _mock_openai, monkeypatch):
        """Empty LLM response → original query returned."""
        from app.rag.query_rewriter import QueryRewriter

        # Make the mock return empty content
        mock = _mock_openai
        fake_choice = type(mock.chat.completions.create.return_value.choices[0])()
        fake_choice.message.content = ""
        mock_response = type(mock.chat.completions.create.return_value)()
        mock_response.choices = [fake_choice]
        mock.chat.completions.create = type(mock.chat.completions.create)(
            return_value=mock_response
        )

        rewriter = QueryRewriter(client=mock)
        result = await rewriter.rewrite("test query")
        assert result == "test query"

    @pytest.mark.asyncio
    async def test_multi_query_returns_list(self, _mock_openai):
        from app.rag.query_rewriter import QueryRewriter
        rewriter = QueryRewriter()
        results = await rewriter.multi_query("年假怎么请?", n=3)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_rewrite_error_returns_original(self, monkeypatch):
        """On API error, rewrite() returns the original query."""
        from app.rag.query_rewriter import QueryRewriter

        rewriter = QueryRewriter()
        # Force an error on the chat.completions.create call
        rewriter._client.chat.completions.create = type(
            rewriter._client.chat.completions.create
        )(side_effect=Exception("API down"))

        result = await rewriter.rewrite("test")
        assert result == "test"


# ============================================================================
# Reranker (with mocked external APIs)
# ============================================================================

class TestReranker:
    """Tests for the cross-encoder reranker with mocked providers."""

    @pytest.mark.asyncio
    async def test_rerank_empty_docs(self):
        from app.rag.reranker import Reranker
        reranker = Reranker(provider="cohere")
        result = await reranker.rerank("query", [], top_k=5)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_cohere_mocked(self, _mock_phase2_deps):
        """With the Cohere mock active, reranking should succeed."""
        from langchain_core.documents import Document as LCDocument

        # Set the API key so the provider doesn't bail early
        from app.config import settings
        from app.rag.reranker import Reranker
        settings.RAG_COHERE_API_KEY = "test-key"

        docs = [
            LCDocument(page_content=f"Document {i}", metadata={"chunk_index": i})
            for i in range(5)
        ]
        reranker = Reranker(provider="cohere")
        result = await reranker.rerank("test query", docs, top_k=3)

        assert len(result) == 1  # mock only returns 1 result
        assert isinstance(result[0][0], LCDocument)
        assert isinstance(result[0][1], float)

    @pytest.mark.asyncio
    async def test_rerank_bge_mocked(self, _mock_phase2_deps):
        from langchain_core.documents import Document as LCDocument

        from app.rag.reranker import Reranker

        docs = [
            LCDocument(page_content=f"Doc {i}", metadata={"chunk_index": i})
            for i in range(5)
        ]
        reranker = Reranker(provider="bge")
        result = await reranker.rerank("test", docs, top_k=3)

        assert len(result) == 3
        # BGE mock returns descending scores [0.9, 0.8, 0.7, ...]
        assert result[0][1] >= result[1][1]

    @pytest.mark.asyncio
    async def test_rerank_jina_mocked(self, _mock_phase2_deps):
        from langchain_core.documents import Document as LCDocument

        from app.config import settings
        from app.rag.reranker import Reranker

        settings.RAG_JINA_API_KEY = "test-key"

        docs = [
            LCDocument(page_content=f"Doc {i}", metadata={"chunk_index": i})
            for i in range(5)
        ]
        reranker = Reranker(provider="jina")
        result = await reranker.rerank("test", docs, top_k=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rerank_unknown_provider_falls_back(self):
        from langchain_core.documents import Document as LCDocument

        from app.rag.reranker import Reranker

        docs = [LCDocument(page_content="x", metadata={})]
        reranker = Reranker(provider="unknown_provider")
        result = await reranker.rerank("q", docs, top_k=1)
        assert len(result) == 1


# ============================================================================
# Integration — Phase 2 pipeline end-to-end (all flags disabled)
# ============================================================================

class TestPhase2Integration:
    """Verify that with Phase 2 flags OFF the existing pipeline still works."""

    @pytest.mark.asyncio
    async def test_ask_query_with_phase2_disabled(self, async_client):
        """Existing ask endpoint works unchanged."""
        payload = {
            "question": "年假怎么申请?",
            "top_k": 5,
            "stream": False,
        }
        response = await async_client.post("/api/v1/queries", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "query_id" in data
        assert "answer" in data
        assert "sources" in data

    @pytest.mark.asyncio
    async def test_retrieve_only_with_phase2_disabled(self, async_client):
        """Existing retrieve endpoint works unchanged."""
        payload = {"question": "报销流程", "top_k": 3}
        response = await async_client.post("/api/v1/queries/retrieve", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "count" in data

    @pytest.mark.asyncio
    async def test_phase2_flags_default_disabled(self):
        """Verify all Phase 2 config flags default to False."""
        from app.config import settings
        assert settings.RAG_HYBRID_SEARCH_ENABLED is False
        assert settings.RAG_RERANKER_ENABLED is False
        assert settings.RAG_QUERY_REWRITE_ENABLED is False
        assert settings.RAG_MULTI_QUERY_ENABLED is False
