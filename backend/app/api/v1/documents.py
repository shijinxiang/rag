"""
=============================================================================
Documents API — Upload, list, get, delete documents
=============================================================================
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.deps import get_document_service
from app.models.document import Document
from app.schemas.common import ErrorResponse, PaginationResponse
from app.schemas.document import (
    DocumentChunkRead,
    DocumentList,
    DocumentRead,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def upload_document(
    file: UploadFile = File(..., description="Document file (PDF, MD, TXT, DOCX)"),
    department: Optional[str] = Query(None, description="Department tag for filtering"),
    access_level: int = Query(0, ge=0, le=2, description="Access level (0=public)"),
    doc_service: DocumentService = Depends(get_document_service),
):
    """
    Upload a document for RAG indexing.

    Supported formats: PDF, Markdown (.md), Text (.txt), Word (.docx).
    The document will be parsed, chunked, embedded, and stored in the vector database.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename.")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "md", "txt", "docx"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Supported: pdf, md, txt, docx",
        )

    doc = await doc_service.upload_document(
        file=file,
        department=department,
        access_level=access_level,
    )

    return DocumentUploadResponse(
        id=doc.id,
        title=doc.title,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        chunk_count=doc.chunk_count,
    )


@router.get("", response_model=DocumentList)
async def list_documents(
    department: Optional[str] = Query(None, description="Filter by department"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    doc_service: DocumentService = Depends(get_document_service),
):
    """List all uploaded documents with optional filters and pagination."""
    documents, total = await doc_service.list_documents(
        department=department,
        status=status_filter,
        page=page,
        page_size=page_size,
    )

    return DocumentList(
        items=[DocumentRead.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get(
    "/{doc_id}",
    response_model=DocumentRead,
    responses={404: {"model": ErrorResponse}},
)
async def get_document(
    doc_id: uuid.UUID,
    doc_service: DocumentService = Depends(get_document_service),
):
    """Get a single document's metadata."""
    doc = await doc_service.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    return DocumentRead.model_validate(doc)


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_document(
    doc_id: uuid.UUID,
    doc_service: DocumentService = Depends(get_document_service),
):
    """Delete a document and all its chunks, embeddings, and files."""
    deleted = await doc_service.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    return None


@router.get(
    "/{doc_id}/chunks",
    response_model=list[DocumentChunkRead],
    responses={404: {"model": ErrorResponse}},
)
async def get_document_chunks(
    doc_id: uuid.UUID,
    doc_service: DocumentService = Depends(get_document_service),
):
    """Get all chunks for a document (useful for debugging retrieval)."""
    doc = await doc_service.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    chunks = await doc_service.get_chunks(doc_id)
    return [DocumentChunkRead.model_validate(c) for c in chunks]
