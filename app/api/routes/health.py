"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    """
    Health check endpoint for load balancers and monitoring.

    Returns:
        Status indicator confirming the API is operational.
    """
    return {"status": "ok"}
