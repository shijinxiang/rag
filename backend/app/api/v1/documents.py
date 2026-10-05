"""
=============================================================================
Documents API — Upload, list, get, delete documents
=============================================================================
"""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_document_service, require_department
from app.db.session import get_db
from app.models.document import Document
from app.models.enterprise import ReviewRequest, ReviewStatus
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.document import (
    DocumentChunkRead,
    DocumentList,
    DocumentRead,
    DocumentUploadResponse,
)
from app.services.audit_service import record_audit
from app.services.document_service import DocumentService
from app.tasks.celery_app import process_document

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="Document file (PDF, MD, TXT, DOCX)"),
    department: str | None = Query(None, description="Department tag for filtering"),
    access_level: int = Query(0, ge=0, le=2, description="Access level (0=public)"),
    doc_service: DocumentService = Depends(get_document_service),
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document for RAG indexing.

    Supported formats: PDF, Markdown (.md), Text (.txt), Word (.docx).
    The document will be parsed, chunked, embedded, and stored in the vector database.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename.")

    require_department(user, department or user.department, manage=True)

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "md", "txt", "docx"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Supported: pdf, md, txt, docx",
        )

    doc = await doc_service.upload_document(
        file=file,
        department=department if user.role == "admin" else user.department,
        access_level=access_level if user.role == "admin" else min(access_level, 1),
        process_inline=False,
    )
    try:
        process_document.delay(str(doc.id))
    except Exception as exc:
        doc.status = "error"
        doc.error_message = "Document processing could not be queued."
        await db.flush()
        await record_audit(db, user_id=user.id, action="document.queue_failed", resource_type="document", resource_id=str(doc.id), outcome="error", request=request, metadata={"error_type": type(exc).__name__})
        await db.commit()
        raise HTTPException(status_code=503, detail="Document processing queue unavailable") from exc
    await record_audit(db, user_id=user.id, action="document.upload", resource_type="document", resource_id=str(doc.id), request=request, metadata={"title": doc.title})
    await db.commit()

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
    department: str | None = Query(None, description="Filter by department"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    doc_service: DocumentService = Depends(get_document_service),
    user: User = Depends(get_authenticated_user),
):
    """List all uploaded documents with optional filters and pagination."""
    if user.role != "admin" and department and department != user.department:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    documents, total = await doc_service.list_documents(
        department=department if user.role == "admin" else (user.department or "__unassigned__"),
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
    user: User = Depends(get_authenticated_user),
):
    """Get a single document's metadata."""
    doc = await doc_service.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    require_department(user, doc.department)
    return DocumentRead.model_validate(doc)


class RetryResponse(BaseModel):
    id: uuid.UUID
    status: str


@router.post("/{doc_id}/retry", response_model=RetryResponse, status_code=202)
async def retry_document(
    doc_id: uuid.UUID,
    request: Request,
    doc_service: DocumentService = Depends(get_document_service),
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await doc_service.get_document(doc_id, for_update=True)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    require_department(user, doc.department, manage=True)
    if doc.status != "error":
        raise HTTPException(status_code=409, detail="Only failed documents can be retried")
    doc.status = "pending"
    doc.error_message = None
    await db.commit()
    try:
        process_document.delay(str(doc.id))
    except Exception as exc:
        doc.status = "error"
        doc.error_message = "Document processing could not be queued."
        await db.commit()
        raise HTTPException(status_code=503, detail="Document processing queue unavailable") from exc
    await record_audit(db, user_id=user.id, action="document.retry", resource_type="document", resource_id=str(doc.id), request=request)
    await db.commit()
    return RetryResponse(id=doc.id, status=doc.status)


@router.post("/{doc_id}/review", status_code=202)
async def request_document_review(
    doc_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    require_department(user, document.department)
    review = ReviewRequest(
        user_id=user.id,
        action="document.delete",
        payload={"document_id": str(document.id), "department": document.department},
        status=ReviewStatus.PENDING,
    )
    db.add(review)
    await db.flush()
    await record_audit(db, user_id=user.id, action="review.request", resource_type="review_request", resource_id=str(review.id), request=request)
    await db.commit()
    return {"id": review.id, "status": review.status}


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_document(
    doc_id: uuid.UUID,
    request: Request,
    doc_service: DocumentService = Depends(get_document_service),
    user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and all its chunks, embeddings, and files."""
    doc = await doc_service.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    require_department(user, doc.department, manage=True)
    deleted = await doc_service.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    await record_audit(db, user_id=user.id, action="document.delete", resource_type="document", resource_id=str(doc_id), request=request)
    await db.commit()
    return None


@router.get(
    "/{doc_id}/chunks",
    response_model=list[DocumentChunkRead],
    responses={404: {"model": ErrorResponse}},
)
async def get_document_chunks(
    doc_id: uuid.UUID,
    doc_service: DocumentService = Depends(get_document_service),
    user: User = Depends(get_authenticated_user),
):
    """Get all chunks for a document (useful for debugging retrieval)."""
    doc = await doc_service.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    require_department(user, doc.department)
    chunks = await doc_service.get_chunks(doc_id)
    return [DocumentChunkRead.model_validate(c) for c in chunks]
