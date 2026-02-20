"""Health check endpoints."""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db import get_db
from app.users.models import User

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Resposta básica de health check."""

    status: str = Field(..., description="Indica se a API está operacional (ok)")


class HealthDbResponse(BaseModel):
    """Resposta do health check com verificação de banco."""

    status: str = Field(..., description="Status da API")
    database: str = Field(..., description="Status da conexão com o banco (connected)")


class HealthProtectedResponse(BaseModel):
    """Resposta do health check protegido (requer autenticação)."""

    status: str = Field(..., description="Status da API")
    message: str = Field(..., description="Mensagem indicando que o endpoint é protegido")
    user_id: str = Field(..., description="UUID do usuário autenticado")
    user_email: str = Field(..., description="E-mail do usuário autenticado")


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Verifica se a API está no ar. **Público** — não exige autenticação. Útil para load balancers, monitoramento e deploy.",
    responses={200: {"description": "API operacional"}},
)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/db",
    response_model=HealthDbResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check (banco de dados)",
    description="Verifica se a API está no ar e se a conexão com o **PostgreSQL** está ativa (executa `SELECT 1`). Público.",
    responses={
        200: {"description": "API e banco operacionais"},
        503: {"description": "Banco indisponível (erro ao conectar)"},
    },
)
def healthcheck_db(db: Session = Depends(get_db)) -> HealthDbResponse:
    db.execute(text("SELECT 1"))
    return HealthDbResponse(status="ok", database="connected")


@router.get(
    "/health/protected",
    response_model=HealthProtectedResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check protegido",
    description="Health check que **exige autenticação** (header `Authorization: Bearer <token>`). Retorna dados do usuário autenticado. Útil para validar que o token está válido.",
    responses={
        200: {"description": "Token válido; API e usuário ok"},
        401: {"description": "Token ausente ou inválido"},
    },
)
def healthcheck_protected(
    current_user: User = Depends(get_current_active_user),
) -> HealthProtectedResponse:
    return HealthProtectedResponse(
        status="ok",
        message="This is a protected endpoint",
        user_id=str(current_user.id),
        user_email=current_user.email or "",
    )
