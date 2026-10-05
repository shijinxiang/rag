"""
=============================================================================
Cross-database compatible types — PostgreSQL types in production,
SQLite-compatible types in tests.
=============================================================================
"""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB


def _is_sqlite() -> bool:
    """Return True if the current DATABASE_URL is SQLite."""
    from app.config import settings

    url = (settings.DATABASE_URL or "").strip()
    return url.startswith("sqlite")


def JSONCompat():
    """Return JSONB on PostgreSQL or plain JSON on SQLite."""
    return JSONB().with_variant(JSON(none_as_null=True), "sqlite")


def NullableVector(dim: int):
    """
    Return a pgvector Vector column on PostgreSQL, or a plain Float column on
    SQLite (for test compatibility).  On SQLite the embeddings table won't
    support ANN search, but test code that doesn't rely on vector similarity
    can still run.
    """
    # Lazy import so pgvector isn't required on SQLite-only test runs
    from pgvector.sqlalchemy import Vector

    return Vector(dim).with_variant(JSON(), "sqlite")
