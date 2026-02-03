"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db import get_db
from app.users.models import User

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    """
    Health check endpoint for load balancers and monitoring.

    Returns:
        Status indicator confirming the API is operational.
    """
    return {"status": "ok"}


@router.get("/health/db")
def healthcheck_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Database health check - verifies connection and session injection.

    Returns:
        Status indicator confirming the database is reachable.
    """
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@router.get("/health/protected")
def healthcheck_protected(
    current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    """
    Protected health check - requires authentication.

    This endpoint demonstrates route protection using JWT authentication.

    Returns:
        Status indicator with user information.
    """
    return {
        "status": "ok",
        "message": "This is a protected endpoint",
        "user_id": str(current_user.id),
        "user_email": current_user.email,
    }
