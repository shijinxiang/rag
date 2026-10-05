"""Administrator-only audit and human review endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user
from app.db.session import get_db
from app.models.document import Document
from app.models.enterprise import ReviewRequest, ReviewStatus
from app.models.user import User
from app.schemas.enterprise import AuditLogRead, ReviewDecision, ReviewRead
from app.services.audit_service import list_audits, record_audit
from app.services.document_service import DocumentService
from app.tasks.celery_app import process_document

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(user: User = Depends(get_authenticated_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


@router.get("/audit-logs", response_model=list[AuditLogRead])
async def audit_logs(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await list_audits(db, limit)


@router.get("/reviews", response_model=list[ReviewRead])
async def reviews(
    status_filter: str = Query(ReviewStatus.PENDING, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(ReviewRequest).where(ReviewRequest.status == status_filter).order_by(ReviewRequest.created_at.desc())
    )
    return list(result.scalars().all())


async def decide_review(
    review_id: uuid.UUID,
    decision: ReviewDecision,
    new_status: str,
    db: AsyncSession,
    admin: User,
    request: Request,
) -> ReviewRequest:
    review = (await db.execute(select(ReviewRequest).where(ReviewRequest.id == review_id).with_for_update())).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="Review request not found")
    if review.status != ReviewStatus.PENDING:
        raise HTTPException(status_code=409, detail="Review request is already decided")
    review.status = new_status
    review.reviewer_id = admin.id
    review.decision_note = decision.note
    await record_audit(
        db,
        user_id=admin.id,
        action=f"review.{new_status}",
        resource_type="review_request",
        resource_id=str(review.id),
        metadata={"request_user_id": str(review.user_id)},
        request=request,
    )
    if new_status == ReviewStatus.APPROVED and review.action == "document.delete":
        document_id = review.payload.get("document_id")
        document = await db.get(Document, uuid.UUID(document_id))
        if document is None:
            raise HTTPException(status_code=404, detail="Reviewed document no longer exists")
        await DocumentService(db).delete_document(document.id)
    elif new_status == ReviewStatus.APPROVED and review.action == "document.reprocess":
        document_id = review.payload.get("document_id")
        try:
            process_document.delay(str(document_id))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Document processing queue unavailable") from exc
    await db.commit()
    return review


@router.post("/reviews/{review_id}/approve", response_model=ReviewRead)
async def approve_review(
    review_id: uuid.UUID,
    decision: ReviewDecision,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await decide_review(review_id, decision, ReviewStatus.APPROVED, db, admin, request)


@router.post("/reviews/{review_id}/reject", response_model=ReviewRead)
async def reject_review(
    review_id: uuid.UUID,
    decision: ReviewDecision,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await decide_review(review_id, decision, ReviewStatus.REJECTED, db, admin, request)
