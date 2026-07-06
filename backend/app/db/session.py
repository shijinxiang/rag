"""
=============================================================================
Database Session — SQLAlchemy async engine + session factory (lazy init)
=============================================================================
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Lazily-initialized engine — avoids importing PostgreSQL driver at import time
# so tests can override DATABASE_URL before the engine is created.
_engine: Optional[AsyncEngine] = None
_AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def _is_sqlite(url: str) -> bool:
    """Return True if the URL is a SQLite connection."""
    return url.startswith("sqlite")


def _get_engine() -> AsyncEngine:
    """Return the async engine, creating it on first call.

    PostgreSQL connections get pooling; SQLite gets no pooling (compatibility
    with in-memory / test databases)."""
    global _engine
    if _engine is None:
        url = settings.DATABASE_URL
        if _is_sqlite(url):
            _engine = create_async_engine(url, echo=settings.APP_DEBUG)
        else:
            _engine = create_async_engine(
                url,
                echo=settings.APP_DEBUG,
                pool_size=20,
                max_overflow=10,
                pool_pre_ping=True,
            )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory, creating it on first call."""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _AsyncSessionLocal


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields an async database session."""
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Dispose the engine (called during app shutdown)."""
    global _engine, _AsyncSessionLocal
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _AsyncSessionLocal = None
