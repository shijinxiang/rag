"""
=============================================================================
Test Fixtures — Shared fixtures for pytest
=============================================================================
"""
import uuid
from collections.abc import AsyncGenerator
from typing import Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models.base import Base

# Use SQLite in-memory for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_rag.db"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh test database session for each test."""
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing FastAPI endpoints."""
    # Override the get_db dependency to use test_db
    from app.db.session import get_db

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_pdf_path(tmp_path) -> str:
    """Create a minimal text file for testing (PDF parsing requires real PDFs)."""
    file_path = tmp_path / "test_doc.txt"
    file_path.write_text(
        "第一章 公司制度\n\n"
        "第一条 员工应遵守公司规章制度。\n\n"
        "第二条 年假申请流程：员工需提前3个工作日通过OA系统提交年假申请，"
        "经直属领导审批后生效。\n\n"
        "第三条 出差报销需提交出差审批单、交通票据、住宿发票和出差报告。\n\n"
        "第二章 薪资福利\n\n"
        "第四条 公司实行薪酬保密制度。\n\n"
        "第五条 年终奖根据员工年度绩效考核结果发放。\n",
        encoding="utf-8",
    )
    return str(file_path)


@pytest.fixture
def sample_doc_id() -> str:
    return str(uuid.uuid4())
