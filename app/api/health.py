"""Health readiness route."""

from fastapi import APIRouter
from app.schemas.response import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, status_code=200)
async def health_check() -> HealthResponse:
    """Readiness probe for judge harness."""
    return HealthResponse(status="ok")
