"""Small persistence helpers for audit events."""
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    outcome: str = "success",
    request_method: str | None = None,
    request_path: str | None = None,
    metadata: dict | None = None,
    request: Request | None = None,
) -> AuditLog:
    request_metadata = {}
    if request is not None:
        request_method = request.method
        request_path = request.url.path
        request_metadata = {"client_ip": request.client.host if request.client else None, "user_agent": request.headers.get("user-agent", "")[:512]}
    event = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        request_method=request_method,
        request_path=request_path,
        metadata_json={**request_metadata, **(metadata or {})},
        created_at=datetime.now(UTC),
    )
    db.add(event)
    await db.flush()
    return event


async def list_audits(db: AsyncSession, limit: int = 100) -> list[AuditLog]:
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    return list(result.scalars().all())
