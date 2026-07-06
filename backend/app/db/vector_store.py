"""
=============================================================================
Vector Store — pgvector wrapper via LangChain PGVector
=============================================================================
Unified vector store interface supporting pgvector as primary backend.
"""
from __future__ import annotations

import uuid
from typing import Optional

from langchain_core.documents import Document as LCDocument
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
from sqlalchemy import text

from app.config import settings


class VectorStore:
    """Unified vector store facade over pgvector (LangChain PGVector)."""

    def __init__(self):
        self._embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        self._store: Optional[PGVector] = None
        self._collection_name = "rag_documents"

    @property
    def embeddings(self) -> OpenAIEmbeddings:
        return self._embeddings

    @property
    def store(self) -> PGVector:
        if self._store is None:
            self._store = PGVector(
                embeddings=self._embeddings,
                collection_name=self._collection_name,
                connection=settings.DATABASE_URL_SYNC,
                pre_delete_collection=False,
            )
        return self._store

    @property
    def is_available(self) -> bool:
        """Return False when running on SQLite (vector search unavailable)."""
        url = (settings.DATABASE_URL or "").strip()
        return not url.startswith("sqlite")

    def add_documents(self, documents: list[LCDocument]) -> list[str]:
        """
        Add documents to the vector store (embeds + inserts).

        Returns list of vector store IDs.
        """
        if not documents:
            return []
        return self.store.add_documents(documents)

    def similarity_search(
        self,
        query: str,
        k: int = 10,
        filter: dict | None = None,
    ) -> list[LCDocument]:
        """
        Perform similarity search with optional metadata filtering.

        Args:
            query: Search query text.
            k: Number of top results.
            filter: Metadata filter dict, e.g. {"department": "hr"}.
        """
        return self.store.similarity_search(query, k=k, filter=filter)

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 10,
        filter: dict | None = None,
    ) -> list[tuple[LCDocument, float]]:
        """Similarity search returning (document, score) tuples."""
        return self.store.similarity_search_with_score(query, k=k, filter=filter)

    def delete_by_doc_id(self, doc_id: str) -> None:
        """Delete all vectors associated with a document ID."""
        # Use SQLAlchemy to delete chunks by doc_id
        # PGVector stores metadata, so we filter and delete
        self.store.delete(filter={"doc_id": doc_id})

    def delete_collection(self) -> None:
        """Delete the entire vector collection."""
        self.store.delete_collection()

    def document_count(self) -> int:
        """Return the number of documents in the vector store."""
        try:
            # PGVector doesn't have a direct count method, use internal table
            with self.store._get_connection() as conn:
                result = conn.execute(
                    text(f"SELECT count(*) FROM langchain_pg_embedding WHERE collection_id = "
                         f"(SELECT uuid FROM langchain_pg_collection WHERE name = :name)"),
                    {"name": self._collection_name},
                )
                return result.scalar() or 0
        except Exception:
            return 0


# Singleton instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return the global VectorStore singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
