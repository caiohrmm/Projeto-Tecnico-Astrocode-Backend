"""Application factory for FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health
from app.attendances.routes import router as attendances_router
from app.auth.routes import router as auth_router
from app.clients.routes import router as clients_router
from app.config.settings import get_settings
from app.core.logging import get_logger, setup_logging
from app.properties.routes import router as properties_router
from app.users.routes import router as users_router
from app.visits.routes import router as visits_router

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
    app.include_router(auth_router)
    app.include_router(attendances_router)
    app.include_router(clients_router)
    app.include_router(properties_router)
    app.include_router(visits_router)
    app.include_router(users_router)

    return app


app = create_app()
