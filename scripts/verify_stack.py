"""Verify a running local stack without calling an external LLM service.

Run inside the backend container with the scripts directory mounted at /checks.
Only uniquely named records created by this check are removed.
"""
import secrets
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.orm import Session

sys.path.insert(0, "/app")

from app.config import settings
from app.db.vector_store import get_vector_store
from app.models.document import Document, DocumentChunk
from app.models.enterprise import AuditLog, ReviewRequest
from app.models.user import User
from app.tasks.celery_app import process_document


def main():
    engine = create_engine(settings.DATABASE_URL_SYNC)
    created_users = []
    created_docs = []
    suffix = uuid.uuid4().hex
    password = secrets.token_urlsafe(18)
    client = httpx.Client(base_url="http://127.0.0.1:8000/api/v1", timeout=20)

    def account(role, department):
        username = f"verify-{role}-{suffix}"
        response = client.post("/auth/register", json={"username": username, "email": f"{username}@example.com", "password": password, "department": department})
        assert response.status_code == 201, response.text
        data = response.json()
        user_id = uuid.UUID(data["user"]["id"])
        created_users.append(user_id)
        with Session(engine) as db:
            db.execute(update(User).where(User.id == user_id).values(role=role))
            db.commit()
        login = client.post("/auth/login", json={"username": username, "password": password})
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['access_token']}"}, data

    try:
        assert client.get("/health").status_code == 200
        assert client.get("/documents").status_code == 401
        employee, emp_data = account("employee", "verify-hr")
        manager, _ = account("manager", "verify-hr")
        admin, _ = account("admin", "verify-finance")
        assert client.get("/auth/me", headers=employee).json()["role"] == "employee"
        assert client.post("/auth/refresh", json={"refresh_token": emp_data["refresh_token"]}).status_code == 200
        assert client.get("/admin/reviews", headers=manager).status_code == 403
        assert client.post("/documents/upload", files={"file": ("empty.txt", b"")}, headers=employee).status_code == 403

        response = client.post("/documents/upload", files={"file": ("verify-empty.txt", b"")}, headers=manager)
        assert response.status_code == 201, response.text
        queued_id = response.json()["id"]
        created_docs.append(uuid.UUID(queued_id))
        assert response.json()["status"] == "pending"
        for _ in range(30):
            doc = client.get(f"/documents/{queued_id}", headers=manager).json()
            if doc["status"] == "error":
                break
            time.sleep(1)
        assert doc["status"] == "error", doc
        assert "no chunks" in doc["error_message"].lower(), doc
        assert client.get("/documents?department=verify-finance", headers=manager).status_code == 403
        assert client.post(f"/documents/{queued_id}/retry", headers=manager).status_code == 202
        for _ in range(30):
            doc = client.get(f"/documents/{queued_id}", headers=manager).json()
            if doc["status"] == "error":
                break
            time.sleep(1)
        assert doc["status"] == "error"

        path = Path("/app/data/uploads") / f"verify-{suffix}.txt"
        path.write_text("Annual leave must be requested three working days in advance.", encoding="utf-8")
        with Session(engine) as db:
            indexed = Document(title=path.name, file_type="txt", file_size=path.stat().st_size, file_path=str(path), department="verify-finance", status="pending")
            db.add(indexed)
            db.flush()
            indexed_id = str(indexed.id)
            created_docs.append(indexed.id)
            db.commit()
        with patch("app.services.embedding_service.EmbeddingService.embed_documents", AsyncMock(side_effect=lambda texts: [[0.1] * 1536 for _ in texts])):
            assert process_document.run(indexed_id) == indexed_id
            assert process_document.run(indexed_id) == indexed_id
        store = get_vector_store()
        results = store.store.similarity_search_by_vector([0.1] * 1536, k=10, filter={"department": "verify-finance"})
        assert any(doc.metadata["doc_id"] == indexed_id for doc in results)
        assert client.get(f"/documents/{indexed_id}", headers=manager).status_code == 403
        with Session(engine) as db:
            chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(indexed_id))))
            assert len(chunks) == 1 and len(chunks[0].embedding) == 1536
        review = client.post(f"/documents/{queued_id}/review", headers=employee)
        assert review.status_code == 202, review.text
        assert client.post(f"/admin/reviews/{review.json()['id']}/approve", json={}, headers=admin).status_code == 200
        assert client.get(f"/documents/{queued_id}", headers=admin).status_code == 404
        assert client.delete(f"/documents/{indexed_id}", headers=admin).status_code == 204
        assert not store.store.similarity_search_by_vector([0.1] * 1536, k=10, filter={"doc_id": indexed_id})
        assert client.get("/admin/audit-logs", headers=admin).json()
        print("PASS: JWT, refresh, RBAC, real Celery failure/retry, offline pgvector pipeline, review approval, audit, vector deletion")
    finally:
        with Session(engine) as db:
            docs = list(db.scalars(select(Document).where(Document.id.in_(created_docs))))
            for doc in docs:
                Path(doc.file_path).unlink(missing_ok=True)
                get_vector_store().delete_by_doc_id(str(doc.id))
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(created_docs)))
            db.execute(delete(Document).where(Document.id.in_(created_docs)))
            db.execute(delete(ReviewRequest).where(ReviewRequest.user_id.in_(created_users)))
            db.execute(delete(AuditLog).where(AuditLog.user_id.in_(created_users)))
            db.execute(delete(User).where(User.id.in_(created_users)))
            db.commit()
        client.close()
        engine.dispose()


if __name__ == "__main__":
    main()
