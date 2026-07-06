"""
=============================================================================
Health Check API
=============================================================================
"""
from fastapi import APIRouter

from app.config import settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint. Returns app status and version."""
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
    )
