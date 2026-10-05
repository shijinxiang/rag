"""
=============================================================================
V1 Router — Aggregates all v1 API sub-routers
=============================================================================
"""
from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.queries import router as queries_router

router = APIRouter(prefix="/api/v1")

# Health (no prefix)
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(admin_router)

# Documents
router.include_router(documents_router)

# Q&A (includes agent endpoint)
router.include_router(queries_router)
