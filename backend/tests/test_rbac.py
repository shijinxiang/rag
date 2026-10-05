"""Role and department boundaries, including review execution and retry."""
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.api.v1.auth import get_current_user
from app.core.security import create_access_token
from app.main import app
from app.models.document import Document
from app.models.enterprise import AuditLog
from app.models.user import User


async def identity(db, role="employee", department="hr"):
    suffix = uuid.uuid4().hex
    user = User(username=suffix, email=f"{suffix}@example.com", password_hash="unused", role=role, department=department)
    db.add(user)
    await db.flush()
    app.dependency_overrides[get_current_user] = lambda: user
    return user


async def document(db, department="hr", status="ready"):
    doc = Document(title="policy.txt", file_type="txt", file_size=6, file_path="missing-test-file", department=department, status=status)
    db.add(doc)
    await db.flush()
    return doc


@pytest.mark.asyncio
async def test_department_isolation_and_unassigned_user(async_client, test_db):
    own = await document(test_db)
    other = await document(test_db, "finance")
    await identity(test_db)
    response = await async_client.get("/api/v1/documents")
    assert [item["id"] for item in response.json()["items"]] == [str(own.id)]
    assert (await async_client.get(f"/api/v1/documents/{other.id}")).status_code == 403
    assert (await async_client.get(f"/api/v1/documents/{other.id}/chunks")).status_code == 403
    assert (await async_client.post(f"/api/v1/documents/{other.id}/review")).status_code == 403
    await identity(test_db, department=None)
    assert (await async_client.get("/api/v1/documents")).json()["total"] == 0


@pytest.mark.asyncio
async def test_employee_cannot_manage_or_view_admin(async_client, test_db):
    doc = await document(test_db)
    await identity(test_db)
    assert (await async_client.post("/api/v1/documents/upload", files={"file": ("a.txt", b"hello")})).status_code == 403
    assert (await async_client.delete(f"/api/v1/documents/{doc.id}")).status_code == 403
    assert (await async_client.get("/api/v1/admin/audit-logs")).status_code == 403
    assert (await async_client.get("/api/v1/admin/reviews")).status_code == 403


@pytest.mark.asyncio
async def test_manager_department_and_admin_review_execution(async_client, test_db, monkeypatch):
    monkeypatch.setattr("app.services.document_service.get_vector_store", lambda: MagicMock())
    own = await document(test_db)
    other = await document(test_db, "finance")
    await identity(test_db, "manager")
    assert (await async_client.delete(f"/api/v1/documents/{other.id}")).status_code == 403
    assert (await async_client.post("/api/v1/documents/upload?department=finance", files={"file": ("a.txt", b"hello")})).status_code == 403
    review = await async_client.post(f"/api/v1/documents/{own.id}/review")
    assert review.status_code == 202
    await identity(test_db, "admin")
    review_id = review.json()["id"]
    assert (await async_client.post(f"/api/v1/admin/reviews/{review_id}/approve", json={})).status_code == 200
    assert await test_db.get(Document, own.id) is None
    assert (await async_client.post(f"/api/v1/admin/reviews/{review_id}/approve", json={})).status_code == 409
    assert (await async_client.delete(f"/api/v1/documents/{other.id}")).status_code == 204
    audit_events = (await test_db.execute(select(AuditLog))).scalars().all()
    assert audit_events
    assert all(event.request_method and event.request_path for event in audit_events)


@pytest.mark.asyncio
async def test_vector_cleanup_failure_keeps_document(test_db, monkeypatch):
    from app.services.document_service import DocumentService

    doc = await document(test_db)
    store = MagicMock()
    store.delete_by_doc_id.side_effect = RuntimeError("vector store unavailable")
    monkeypatch.setattr("app.services.document_service.get_vector_store", lambda: store)
    with pytest.raises(RuntimeError, match="vector store unavailable"):
        await DocumentService(test_db).delete_document(doc.id)
    assert await test_db.get(Document, doc.id) is doc


@pytest.mark.asyncio
async def test_expired_wrong_type_and_malformed_subject_tokens(async_client):
    app.dependency_overrides.pop(get_current_user, None)
    for token in ["invalid", create_access_token("invalid-uuid", "admin"), create_access_token(str(uuid.uuid4()), "admin", minutes=-1)]:
        assert (await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401
    assert (await async_client.post("/api/v1/auth/refresh", json={"refresh_token": create_access_token("invalid-uuid", "admin")})).status_code == 401


@pytest.mark.asyncio
async def test_retry_commits_pending_before_queue_and_persists_failure(async_client, test_db, monkeypatch):
    doc = await document(test_db, status="error")
    await identity(test_db, "manager")
    task = MagicMock()
    monkeypatch.setattr("app.api.v1.documents.process_document", task)
    response = await async_client.post(f"/api/v1/documents/{doc.id}/retry")
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    task.delay.assert_called_once_with(str(doc.id))
    assert (await async_client.post(f"/api/v1/documents/{doc.id}/retry")).status_code == 409
    doc.status = "error"
    await test_db.flush()
    task.delay.side_effect = RuntimeError("queue down")
    assert (await async_client.post(f"/api/v1/documents/{doc.id}/retry")).status_code == 503
    await test_db.refresh(doc)
    assert doc.status == "error"
    assert doc.error_message


@pytest.mark.asyncio
async def test_query_filters_cannot_be_overridden(async_client, test_db, monkeypatch):
    from unittest.mock import AsyncMock

    from app.api.deps import get_query_service

    await identity(test_db, department="hr")
    service = MagicMock()
    service.retrieve_only = AsyncMock(return_value=[])
    app.dependency_overrides[get_query_service] = lambda: service
    response = await async_client.post("/api/v1/queries/retrieve", json={"question": "test", "department": "finance"})
    assert response.status_code == 200
    assert service.retrieve_only.call_args.kwargs["filters"] == {"department": "hr"}
