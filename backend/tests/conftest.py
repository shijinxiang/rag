"""
=============================================================================
Test Fixtures - Shared fixtures for pytest
=============================================================================

Isolation strategy - TWO separate engines must point at the SAME database file:
  1. *test_engine*: created by conftest, owned by the test framework.  Used to
     create tables (Base.metadata.create_all) and to issue queries in test
     code.
  2. *app engine*: created lazily by app.db.session when the FastAPI app's
     request handlers need a session.

For both engines to see the same tables we use a FILE-based SQLite database
(not :memory: - SQLite :memory: creates a separate database per connection).

A single conftest-level fixture `_test_db_url` writes the test URL into
settings *before* either engine is created, so both point at the same file.
"""
import os
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# 1. The one-and-only test database URL
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def _test_db_url(tmp_path_factory) -> str:
    """Return a file-path SQLite URL that both engines will share."""
    db_dir = tmp_path_factory.mktemp("data")
    return f"sqlite+aiosqlite:///{db_dir / 'test_rag.db'}"


@pytest.fixture(scope="session", autouse=True)
def _patch_settings_for_tests(_test_db_url):
    """Before ANY engine is created, override settings to use the test URL.

    Scope="session" + autouse=True ensures this runs before the session-scoped
    test_engine fixture, which in turn runs before every function-scoped
    async_client fixture.

    We also blow away any previously cached engine so the next call to
    _get_engine() creates a fresh one against the test URL.
    """
    os.environ["DATABASE_URL"] = _test_db_url

    import app.config as _cfg
    _cfg.settings.DATABASE_URL = _test_db_url
    _cfg.settings.DATABASE_URL_SYNC = _test_db_url

    import app.db.session as _sess
    _sess._engine = None
    _sess._AsyncSessionLocal = None


# ---------------------------------------------------------------------------
# 2. Test engine + session
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session")
async def test_engine(_test_db_url):
    """Session-scoped SQLite engine - creates all tables once."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_test_db_url, echo=False)

    from app.models.base import Base
    from app.models.document import Document, DocumentChunk  # noqa: register tables

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator:
    """Per-test session - wrapped in a transaction that rolls back."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# 3. Mock OpenAI (no real API key or HTTP call needed in tests)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _mock_openai(monkeypatch):
    """Mock the AsyncOpenAI client so no real API call is made in tests.

    autouse=True ensures every test gets mocked regardless of explicit markers.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy-key-for-pytest")

    mock_client = AsyncMock()

    # --- mock embeddings.create ---
    fake_embedding = MagicMock()
    fake_embedding.index = 0
    fake_embedding.embedding = [0.1] * 1536
    mock_embeddings_response = MagicMock()
    mock_embeddings_response.data = [fake_embedding]
    mock_client.embeddings.create = AsyncMock(return_value=mock_embeddings_response)

    # --- mock chat.completions.create ---
    fake_choice = MagicMock()
    fake_choice.message.content = "Mock answer for testing."
    mock_chat_response = MagicMock()
    mock_chat_response.choices = [fake_choice]
    mock_chat_response.usage = MagicMock()
    mock_chat_response.usage.prompt_tokens = 100
    mock_chat_response.usage.completion_tokens = 50
    mock_chat_response.usage.total_tokens = 150
    mock_client.chat.completions.create = AsyncMock(return_value=mock_chat_response)

    # Replace AsyncOpenAI constructors so both services get the mock
    monkeypatch.setattr(
        "app.services.embedding_service.AsyncOpenAI",
        lambda *a, **kw: mock_client,
    )
    monkeypatch.setattr(
        "app.services.generation_service.AsyncOpenAI",
        lambda *a, **kw: mock_client,
    )

    return mock_client


# ---------------------------------------------------------------------------
# 4. Async HTTP test client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def async_client(test_db) -> AsyncIterator:
    """FastAPI TestClient whose DB dependency is overridden to test_db."""
    from httpx import ASGITransport, AsyncClient

    from app.db.session import get_db
    from app.main import app

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Sample document helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_txt_path(tmp_path) -> str:
    """A tiny text file for testing document loading."""
    file_path = tmp_path / "test_doc.txt"
    file_path.write_text(
        "Chapter 1: Company Policy\n\n"
        "Article 1: Employees must follow company regulations.\n\n"
        "Article 2: Annual leave must be submitted 3 working days in advance.\n\n"
        "Chapter 2: Compensation\n\n"
        "Article 4: Salary information is confidential.\n",
        encoding="utf-8",
    )
    return str(file_path)


@pytest.fixture
def sample_doc_id() -> str:
    return str(uuid.uuid4())
