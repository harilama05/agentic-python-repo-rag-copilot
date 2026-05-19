"""Health-check route definitions."""

from fastapi import APIRouter

from api.schemas import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return a basic application health response."""
    return HealthResponse()
