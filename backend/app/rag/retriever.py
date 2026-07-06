"""
=============================================================================
Retriever — RAG retrieval facade over VectorStore
=============================================================================
"""
from langchain_core.documents import Document as LCDocument

from app.config import settings
from app.db.vector_store import VectorStore, get_vector_store


class Retriever:
    """RAG retriever with metadata filtering support."""

    def __init__(self, vector_store: VectorStore | None = None):
        self._store = vector_store or get_vector_store()

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        filters: dict | None = None,
    ) -> list[LCDocument]:
        """
        Retrieve top-k documents for a query.

        Args:
            query: User query string.
            top_k: Number of documents to retrieve (defaults to RAG_TOP_K).
            filters: Metadata filter dict, e.g. {"department": "hr", "access_level": 1}.

        Returns:
            List of LangChain Documents with scores.
        """
        k = top_k or settings.RAG_TOP_K
        return self._store.similarity_search(query, k=k, filter=filters)

    def retrieve_with_scores(
        self,
        query: str,
        top_k: int | None = None,
        filters: dict | None = None,
    ) -> list[tuple[LCDocument, float]]:
        """Retrieve documents with similarity scores."""
        k = top_k or settings.RAG_TOP_K
        return self._store.similarity_search_with_score(query, k=k, filter=filters)

    @staticmethod
    def format_context(documents: list[LCDocument]) -> str:
        """Format retrieved documents into a prompt context string."""
        parts = []
        for i, doc in enumerate(documents, 1):
            title = doc.metadata.get("doc_title", "Unknown")
            page = doc.metadata.get("page", "N/A")
            source = doc.metadata.get("source_file", "Unknown")
            parts.append(
                f"--- [文档 {i}] {title} | 页码: {page} | 来源: {source} ---\n{doc.page_content}"
            )
        return "\n\n".join(parts)
