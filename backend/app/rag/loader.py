"""
=============================================================================
Document Loader — Multi-format document loading via LangChain
=============================================================================
Supports: PDF, Markdown, TXT, DOCX
"""
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
    UnstructuredWordDocumentLoader,
)
from langchain_core.documents import Document as LCDocument


class DocumentLoader:
    """Loads documents of various formats into LangChain Document objects."""

    SUPPORTED_TYPES = {"pdf", "md", "txt", "docx"}

    @staticmethod
    def _get_loader(file_path: str, file_type: str):
        """Return the appropriate LangChain loader for the given file type."""
        loaders = {
            "pdf": PyPDFLoader,
            "md": UnstructuredMarkdownLoader,
            "txt": lambda p: TextLoader(p, encoding="utf-8"),
            "docx": UnstructuredWordDocumentLoader,
        }
        loader_cls = loaders.get(file_type)
        if loader_cls is None:
            raise ValueError(
                f"Unsupported file type: '{file_type}'. Supported: {DocumentLoader.SUPPORTED_TYPES}"
            )
        return loader_cls(file_path)

    @classmethod
    def load_document(
        cls,
        file_path: str,
        file_type: str | None = None,
    ) -> list[LCDocument]:
        """
        Load a document file and return a list of LangChain Documents.

        Args:
            file_path: Path to the document file.
            file_type: File extension/type. Auto-detected from path if None.

        Returns:
            List of LangChain Document objects (one per page/section).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        if file_type is None:
            file_type = path.suffix.lstrip(".").lower()

        if file_type not in cls.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported file type: '{file_type}'. Supported: {cls.SUPPORTED_TYPES}"
            )

        loader = cls._get_loader(str(path), file_type)
        documents = loader.load()

        # Ensure each document has the source file_type in metadata
        for doc in documents:
            doc.metadata["file_type"] = file_type
            doc.metadata["source_file"] = path.name

        return documents

    @classmethod
    def load_and_get_text(cls, file_path: str, file_type: str | None = None) -> str:
        """Load a document and return the concatenated full text."""
        docs = cls.load_document(file_path, file_type)
        return "\n\n".join(doc.page_content for doc in docs)
