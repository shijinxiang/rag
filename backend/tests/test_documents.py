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
async def test_upload_unsupported_file(async_client: AsyncClient):
    """Uploading an unsupported file type should fail with 400."""
    files = {"file": ("test.jpg", b"fake-image-data", "image/jpeg")}
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported" in data["detail"] or "unsupported" in str(data).lower()


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
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_queries_ask_empty_question(async_client: AsyncClient):
    """Asking with no documents indexed should still work (graceful fallback)."""
    response = await async_client.post(
        "/api/v1/queries",
        json={"question": "年假怎么申请？"},
    )
    # Should succeed with a response (may say no documents found)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "query_id" in data


@pytest.mark.asyncio
async def test_retrieve_only(async_client: AsyncClient):
    """Retrieve-only endpoint should work without LLM generation."""
    response = await async_client.post(
        "/api/v1/queries/retrieve",
        json={"question": "test query"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0  # No documents indexed yet
    assert data["query"] == "test query"


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Root endpoint returns app info."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "version" in data
