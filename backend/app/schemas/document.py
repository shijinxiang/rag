"""
=============================================================================
Document Pydantic Schemas
=============================================================================
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentRead(BaseModel):
    """Document metadata returned to clients."""
    id: uuid.UUID
    title: str
    file_type: str
    file_size: int
    status: str
    version: int
    department: Optional[str] = None
    access_level: int = 0
    chunk_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentList(BaseModel):
    """Paginated document list."""
    items: list[DocumentRead]
    total: int
    page: int
    page_size: int
    pages: int


class DocumentUploadResponse(BaseModel):
    """Response after a successful document upload."""
    id: uuid.UUID
    title: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    message: str = "Document uploaded and queued for processing."


class DocumentChunkRead(BaseModel):
    """A single document chunk."""
    id: uuid.UUID
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    chunk_metadata: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}
