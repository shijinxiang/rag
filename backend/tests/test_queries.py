"""
=============================================================================
Tests: Q&A Query Pipeline
=============================================================================
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ask_question_basic(async_client: AsyncClient):
    """Basic question with no indexed docs should return a valid response."""
    response = await async_client.post(
        "/api/v1/queries",
        json={"question": "公司年假怎么申请？"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "query_id" in data
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0
    assert "sources" in data
    assert isinstance(data["sources"], list)


@pytest.mark.asyncio
async def test_ask_question_with_top_k(async_client: AsyncClient):
    """Question with custom top_k parameter."""
    response = await async_client.post(
        "/api/v1/queries",
        json={"question": "报销流程", "top_k": 5},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ask_question_with_department_filter(async_client: AsyncClient):
    """Question with department filter parameter."""
    response = await async_client.post(
        "/api/v1/queries",
        json={"question": "薪资政策", "department": "hr"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_response_structure(async_client: AsyncClient):
    """Verify QueryResponse JSON has all expected fields."""
    response = await async_client.post(
        "/api/v1/queries",
        json={"question": "测试问题"},
    )
    assert response.status_code == 200
    data = response.json()

    required = [
        "query_id", "question", "answer", "sources",
        "retrieval_count", "prompt_tokens", "completion_tokens", "total_tokens",
    ]
    for field in required:
        assert field in data, f"Missing field: {field}"

    # Source fields
    for source in data["sources"]:
        assert "index" in source
        assert "doc_title" in source
        assert "score" in source
        assert "excerpt" in source


@pytest.mark.asyncio
async def test_retrieve_with_filters(async_client: AsyncClient):
    """Retrieve with department filter parameter."""
    response = await async_client.post(
        "/api/v1/queries/retrieve",
        json={"question": "安全制度", "department": "security", "top_k": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0  # No docs yet
