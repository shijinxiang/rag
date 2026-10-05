"""
=============================================================================
API Dependencies — FastAPI dependency injection
=============================================================================
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.document_service import DocumentService
from app.services.query_service import QueryService


def user_filters(user: User) -> dict | None:
    if user.role == "admin":
        return None
    if user.department:
        return {"department": user.department}
    return {"department": "__unassigned__"}


def require_department(user: User, department: str | None, *, manage: bool = False) -> None:
    from fastapi import HTTPException

    if user.role == "admin":
        return
    if manage and user.role != "manager":
        raise HTTPException(status_code=403, detail="Manager role required")
    if not user.department or department != user.department:
        raise HTTPException(status_code=403, detail="Insufficient department permissions")


async def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    """Dependency: DocumentService with DB session."""
    return DocumentService(db)


async def get_query_service(db: AsyncSession = Depends(get_db)) -> QueryService:
    """Dependency: QueryService with DB session."""
    return QueryService(db)


async def get_authenticated_user(user: User = Depends(get_current_user)) -> User:
    return user
