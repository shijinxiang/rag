"""
=============================================================================
Text Splitter — Semantic & recursive chunking strategies
=============================================================================
"""
from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


class TextSplitter:
    """Splits documents into overlapping chunks for embedding and retrieval."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        separators: list[str] | None = None,
    ):
        self.chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP
        self.separators = separators or ["\n\n", "\n", "。", ".", " ", ""]

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            length_function=len,
            is_separator_regex=False,
        )

    def split_documents(
        self,
        documents: list[LCDocument],
        doc_id: str | None = None,
        doc_title: str | None = None,
    ) -> list[LCDocument]:
        """
        Split documents into chunks with enriched metadata.

        Args:
            documents: LangChain Documents from loader.
            doc_id: Parent document UUID (added to each chunk's metadata).
            doc_title: Parent document title (added to each chunk's metadata).

        Returns:
            List of chunked LangChain Documents with metadata.
        """
        chunks = self._splitter.split_documents(documents)

        # Enrich each chunk with parent document metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["chunk_count"] = len(chunks)
            if doc_id:
                chunk.metadata["doc_id"] = doc_id
            if doc_title:
                chunk.metadata["doc_title"] = doc_title

        return chunks

    def split_text(self, text: str) -> list[str]:
        """Split a single text string into chunks."""
        return self._splitter.split_text(text)
