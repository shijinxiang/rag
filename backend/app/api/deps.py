"""
=============================================================================
API Dependencies — FastAPI dependency injection
=============================================================================
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.document_service import DocumentService
from app.services.query_service import QueryService


async def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    """Dependency: DocumentService with DB session."""
    return DocumentService(db)


async def get_query_service(db: AsyncSession = Depends(get_db)) -> QueryService:
    """Dependency: QueryService with DB session."""
    return QueryService(db)
