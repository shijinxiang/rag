"""
=============================================================================
V1 Router — Aggregates all v1 API sub-routers
=============================================================================
"""
from fastapi import APIRouter

from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.queries import router as queries_router

router = APIRouter(prefix="/api/v1")

# Health (no prefix)
router.include_router(health_router)

# Documents
router.include_router(documents_router)

# Q&A
router.include_router(queries_router)
