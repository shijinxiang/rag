"""
=============================================================================
Tests: Document API
=============================================================================
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    """Verify health check endpoint returns healthy status."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_list_documents_empty(async_client: AsyncClient):
    """List documents when none exist should return empty list."""
    response = await async_client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_documents_with_params(async_client: AsyncClient):
    """List documents with pagination params."""
    response = await async_client.get("/api/v1/documents?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 10


@pytest.mark.asyncio
async def test_queries_ask_without_docs(async_client: AsyncClient):
    """Q&A without indexed docs should still return a valid response structure."""
    response = await async_client.post(
        "/api/v1/queries",
        json={"question": "年假怎么申请？"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "query_id" in data


@pytest.mark.asyncio
async def test_retrieve_empty(async_client: AsyncClient):
    """Retrieve without indexed docs returns empty list."""
    response = await async_client.post(
        "/api/v1/queries/retrieve",
        json={"question": "test query"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["query"] == "test query"


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Root endpoint returns app info."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_empty_question_rejected(async_client: AsyncClient):
    """Empty question string should be rejected with 422."""
    response = await async_client.post("/api/v1/queries", json={"question": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_too_long_question_rejected(async_client: AsyncClient):
    """Overly long question should be rejected with 422."""
    response = await async_client.post(
        "/api/v1/queries", json={"question": "x" * 6000}
    )
    assert response.status_code == 422
