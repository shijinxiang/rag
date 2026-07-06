"""
=============================================================================
Document & DocumentChunk ORM Models
=============================================================================
"""
import uuid
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class DocumentStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class Document(Base, UUIDMixin, TimestampMixin):
    """Uploaded document metadata."""

    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # pdf, md, txt, docx
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # Bytes
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)  # MinIO object key
    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.PENDING, nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    access_level: Mapped[int] = mapped_column(Integer, default=0)  # 0=public, 1=internal, 2=confidential
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title='{self.title}', status='{self.status}')>"


class DocumentChunk(Base, UUIDMixin, TimestampMixin):
    """A single text chunk from a document."""

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(1536), nullable=True  # pgvector column; dimension matches embedding model
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, doc='{self.document_id}', chunk={self.chunk_index})>"
