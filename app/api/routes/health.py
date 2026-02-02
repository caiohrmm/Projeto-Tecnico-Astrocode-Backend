"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

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
