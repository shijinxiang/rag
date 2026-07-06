"""
=============================================================================
Document Service — Upload, parse, chunk, embed, store orchestration
=============================================================================
"""
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.vector_store import get_vector_store
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.rag.loader import DocumentLoader
from app.rag.splitter import TextSplitter
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


class DocumentService:
    """Orchestrates document upload, parsing, chunking, embedding, and storage."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._splitter = TextSplitter()
        self._embedding_service = EmbeddingService()

    async def upload_document(
        self,
        file: UploadFile,
        department: Optional[str] = None,
        access_level: int = 0,
    ) -> Document:
        """
        Full document upload pipeline:
        1. Save file to disk
        2. Parse with LangChain loader
        3. Split into chunks
        4. Generate embeddings
        5. Store in pgvector + metadata in PostgreSQL

        Args:
            file: Uploaded file from FastAPI.
            department: Department tag for metadata filtering.
            access_level: Access level (0=public, 1=internal, 2=confidential).

        Returns:
            Created Document ORM record.
        """
        # ---- Step 1: Save file ----
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        file_ext = Path(file.filename or "unknown").suffix.lstrip(".").lower()
        saved_path = UPLOAD_DIR / f"{uuid.uuid4()}.{file_ext}"

        content = await file.read()
        saved_path.write_bytes(content)
        file_size = len(content)

        # ---- Step 2: Create Document record ----
        doc = Document(
            title=file.filename or "Untitled",
            file_type=file_ext,
            file_size=file_size,
            file_path=str(saved_path),
            status=DocumentStatus.PROCESSING,
            department=department,
            access_level=access_level,
        )
        self._db.add(doc)
        await self._db.flush()  # Get doc.id

        try:
            # ---- Step 3: Load & Parse ----
            langchain_docs = DocumentLoader.load_document(
                str(saved_path), file_type=file_ext
            )

            # ---- Step 4: Split into chunks ----
            chunks = self._splitter.split_documents(
                langchain_docs,
                doc_id=str(doc.id),
                doc_title=doc.title,
            )

            if not chunks:
                raise ValueError("Document produced no chunks—check file content.")

            # ---- Step 5: Generate embeddings ----
            chunk_texts = [c.page_content for c in chunks]
            embeddings = await self._embedding_service.embed_documents(chunk_texts)

            # ---- Step 6: Store chunks + embeddings ----
            chunk_records = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_record = DocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk.page_content,
                    page_number=chunk.metadata.get("page"),
                    chunk_metadata={
                        "doc_title": doc.title,
                        "source_file": chunk.metadata.get("source_file", ""),
                        "page": chunk.metadata.get("page"),
                        "chunk_index": i,
                        "chunk_count": len(chunks),
                    },
                    embedding=embedding,
                )
                chunk_records.append(chunk_record)

            self._db.add_all(chunk_records)

            # ---- Step 7: Also add to PGVector via LangChain ----
            vector_store = get_vector_store()
            # Prepare LangChain Documents with metadata for PGVector
            lc_docs_for_store = []
            for chunk in chunks:
                chunk.metadata["doc_id"] = str(doc.id)
                chunk.metadata["doc_title"] = doc.title
                lc_docs_for_store.append(chunk)
            vector_store.add_documents(lc_docs_for_store)

            # ---- Step 8: Update Document status ----
            doc.status = DocumentStatus.READY
            doc.chunk_count = len(chunks)
            doc.updated_at = datetime.now(timezone.utc)

            logger.info(
                "Document '%s' processed: %d chunks, %d embeddings",
                doc.title,
                len(chunks),
                len(embeddings),
            )

        except Exception as exc:
            doc.status = DocumentStatus.ERROR
            doc.error_message = str(exc)
            logger.error("Document '%s' processing failed: %s", doc.title, exc)

        await self._db.flush()
        return doc

    async def get_document(self, doc_id: uuid.UUID) -> Optional[Document]:
        """Retrieve a single document by ID."""
        result = await self._db.execute(
            select(Document).where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        department: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int]:
        """List documents with optional filters and pagination."""
        query = select(Document)
        count_query = select(func.count(Document.id))

        if department:
            query = query.where(Document.department == department)
            count_query = count_query.where(Document.department == department)
        if status:
            query = query.where(Document.status == status)
            count_query = count_query.where(Document.status == status)

        # Total count
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = (
            query
            .order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self._db.execute(query)
        documents = list(result.scalars().all())

        return documents, total

    async def delete_document(self, doc_id: uuid.UUID) -> bool:
        """Delete a document and its chunks/embeddings."""
        doc = await self.get_document(doc_id)
        if doc is None:
            return False

        # Remove from vector store
        try:
            vector_store = get_vector_store()
            vector_store.delete_by_doc_id(str(doc_id))
        except Exception as exc:
            logger.warning("Failed to delete vectors for doc %s: %s", doc_id, exc)

        # Delete file from disk
        try:
            file_path = Path(doc.file_path)
            if file_path.exists():
                file_path.unlink()
        except Exception as exc:
            logger.warning("Failed to delete file for doc %s: %s", doc_id, exc)

        # DB cascade will delete chunks
        await self._db.delete(doc)
        await self._db.flush()

        logger.info("Document '%s' (id=%s) deleted.", doc.title, doc_id)
        return True

    async def get_chunks(self, doc_id: uuid.UUID) -> list[DocumentChunk]:
        """Get all chunks for a document."""
        result = await self._db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())
