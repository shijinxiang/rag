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
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

# Project-root-relative directory for test artifacts (SQLite DB, etc.)
# We don't use tmp_path_factory so tests work even when system temp is restricted.
_TEST_ARTIFACTS = Path(__file__).resolve().parent.parent / ".test-artifacts"


# ---------------------------------------------------------------------------
# 1. The one-and-only test database URL
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def _test_db_url() -> str:
    """Return a file-path SQLite URL that both engines will share.

    The database file lives inside the project (backend/.test-artifacts/) so
    tests don't depend on system temp directory permissions.
    """
    _TEST_ARTIFACTS.mkdir(parents=True, exist_ok=True)
    db_path = _TEST_ARTIFACTS / "test_rag.db"
    return f"sqlite+aiosqlite:///{db_path}"


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

    from app import models  # noqa: F401
    from app.models.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncGenerator:
    """Reset tables because queue endpoints deliberately commit before dispatch."""
    from app.models.base import Base

    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
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
    monkeypatch.setattr(
        "app.rag.query_rewriter.AsyncOpenAI",
        lambda *a, **kw: mock_client,
    )

    return mock_client


# ---------------------------------------------------------------------------
# 3b. Mock external Phase 2 dependencies (cohere, BGE, Jina)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _mock_phase2_deps(monkeypatch):
    """Mock Cohere / BGE / Jina clients so tests run without external APIs.

    Each mock is idempotent — if the library isn't installed the monkeypatch
    silently does nothing (import-time guard).
    """

    # --- mock cohere.AsyncClient -----------------------------------------
    try:
        import cohere  # noqa: F401
    except ImportError:
        cohere = None

    if cohere is not None:
        mock_cohere_client = MagicMock()
        fake_rerank_result = MagicMock()
        fake_rerank_result.index = 0
        fake_rerank_result.relevance_score = 0.95
        mock_rerank_response = MagicMock()
        mock_rerank_response.results = [fake_rerank_result]
        mock_cohere_client.rerank = AsyncMock(return_value=mock_rerank_response)
        monkeypatch.setattr(
            "cohere.AsyncClient",
            lambda *a, **kw: mock_cohere_client,
        )

    # --- mock sentence_transformers.CrossEncoder -------------------------
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        sentence_transformers = None

    if sentence_transformers is not None:
        mock_cross_encoder = MagicMock()
        # predict() returns a numpy-like array of scores
        mock_cross_encoder.predict = MagicMock(return_value=[0.9, 0.8, 0.7, 0.6, 0.5])
        monkeypatch.setattr(
            "sentence_transformers.CrossEncoder",
            lambda *a, **kw: mock_cross_encoder,
        )

    # --- mock httpx.AsyncClient for Jina API -----------------------------
    try:
        import httpx  # noqa: F401
    except ImportError:
        httpx = None  # type: ignore[assignment]

    if httpx is not None:
        _original_async_client = httpx.AsyncClient

        class _MockJinaAsyncClient(_original_async_client):
            """Intercept POSTs to api.jina.ai and return a fake rerank result."""

            async def post(self, url, **kwargs):
                if "api.jina.ai" in str(url):
                    mock_resp = MagicMock()
                    mock_resp.raise_for_status = MagicMock()
                    mock_resp.json = MagicMock(return_value={
                        "results": [
                            {"index": 0, "relevance_score": 0.95},
                            {"index": 1, "relevance_score": 0.82},
                            {"index": 2, "relevance_score": 0.71},
                        ]
                    })
                    return mock_resp
                return await super().post(url, **kwargs)

        monkeypatch.setattr("httpx.AsyncClient", _MockJinaAsyncClient)


# ---------------------------------------------------------------------------
# 4. Async HTTP test client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def async_client(test_db) -> AsyncIterator:
    """FastAPI TestClient whose DB dependency is overridden to test_db."""
    from httpx import ASGITransport, AsyncClient

    from app.api.v1.auth import get_current_user
    from app.db.session import get_db
    from app.main import app
    from app.models.user import User, UserRole

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    test_user = User(
        username="test-admin",
        email="test-admin@example.com",
        password_hash="unused",
        role=UserRole.ADMIN,
    )
    test_user.id = uuid.uuid4()
    app.dependency_overrides[get_current_user] = lambda: test_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Sample document helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_txt_path() -> str:
    """A tiny text file for testing document loading."""
    file_dir = _TEST_ARTIFACTS / "sample_docs"
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / "test_doc.txt"
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
