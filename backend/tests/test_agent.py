"""Focused tests for Agent routing and review behavior."""

import pytest


def test_route_after_classify_uses_retrieval_by_default():
    from app.agent.nodes import route_after_classify

    assert route_after_classify({"classification": "retrieval_qa"}) == "retrieve"
    assert route_after_classify({"classification": "general_chat"}) == "generate"
    assert route_after_classify({"classification": "document_operation"}) == "review"


def test_review_requires_explicit_approval_for_document_operation():
    from app.agent.nodes import route_after_review

    assert route_after_review({"review_approved": False}) == "__end__"
    assert route_after_review({"review_approved": True}) == "generate"


@pytest.mark.asyncio
async def test_document_operation_review_is_pending_by_default():
    from app.agent.nodes import review_node

    state = {"question": "删除文档", "classification": "document_operation"}
    result = await review_node(state)

    assert result["review_status"] == "pending"
    assert result["review_approved"] is False


@pytest.mark.asyncio
async def test_tool_node_records_allowlisted_search(monkeypatch):
    from app.agent import nodes

    async def fake_invoke(query, top_k, department=None):
        assert query == "年假怎么申请"
        assert top_k == 5
        return "检索结果"

    monkeypatch.setattr(nodes.search_knowledge, "coroutine", fake_invoke)
    result = await nodes.tool_node(
        {"question": "年假怎么申请", "classification": "retrieval_qa", "top_k": 5}
    )

    assert result["tool_result"] == "检索结果"
    assert result["tool_calls"][0]["name"] == "search_knowledge"
