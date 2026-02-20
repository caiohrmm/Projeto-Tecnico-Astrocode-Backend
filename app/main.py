"""Application factory for FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.routes import router as ai_summaries_router
from app.ai.chat_router import router as ai_chat_router, shutdown_executor
from app.ai.journey_routes import router as ai_journey_router
from app.api.routes import health
from app.attendances.routes import router as attendances_router
from app.auth.routes import router as auth_router
from app.clients.routes import router as clients_router
from app.config.settings import get_settings
from app.core.logging import get_logger, setup_logging
from app.losses.routes import router as losses_router
from app.properties.routes import router as properties_router
from app.sales.routes import router as sales_router
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
    # Cleanup thread pool executor for Gemini API calls
    shutdown_executor()
    logger.info("Thread pool executor shut down")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Uses the application factory pattern for testability and
    flexible configuration.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="""
API REST do **CRM Imobiliário** com IA integrada (Google Gemini).

## Recursos principais
- **Autenticação:** login, registro, recuperação de senha, OAuth Google
- **Clientes:** CRUD, derivação de estado (lead score, status), timeline
- **Atendimentos:** ciclos de atendimento (um ativo por cliente), resumos IA
- **Imóveis:** CRUD, geocoding, upload de imagens (Cloudinary)
- **Visitas, vendas e perdas:** vinculados a cliente e atendimento
- **IA:** resumos, chat contextual, jornada do cliente, recomendações

## Autenticação na API
Endpoints protegidos exigem o header: `Authorization: Bearer <token>`.
Token obtido em `POST /auth/login` ou `POST /auth/public/register` ou fluxo Google.
        """.strip(),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS (origins from settings: localhost by default, set CORS_ORIGINS on Render)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth_router)
    app.include_router(attendances_router)
    app.include_router(ai_summaries_router)
    app.include_router(ai_chat_router)
    app.include_router(ai_journey_router)
    app.include_router(clients_router)
    app.include_router(losses_router)
    app.include_router(properties_router)
    app.include_router(sales_router)
    app.include_router(visits_router)
    app.include_router(users_router)

    return app


app = create_app()
