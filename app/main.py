"""Application factory for FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health
from app.config.settings import get_settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    setup_logging()
    logger.info("Application starting up")
    yield
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Uses the application factory pattern for testability and
    flexible configuration.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Backend de auxílio ao atendimento em imobiliárias",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
    )

    app.include_router(health.router)

    return app


app = create_app()
