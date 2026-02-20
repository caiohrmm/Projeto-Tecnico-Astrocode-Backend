"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, get_current_manager
from app.auth.oauth_service import OAuthService
from app.auth.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
)
from app.auth.service import AuthService
from app.db import get_db
from app.users.models import User
from app.users.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login",
    description="Autentica com e-mail e senha. Retorna um token JWT para usar no header **Authorization: Bearer &lt;token&gt;** nas demais requisições.",
    responses={
        200: {"description": "Token JWT retornado"},
        401: {"description": "Credenciais inválidas"},
        422: {"description": "Dados de entrada inválidos"},
    },
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    auth_service = AuthService(db)
    token_data = auth_service.authenticate_user(
        email=login_data.email,
        password=login_data.password,
    )
    return TokenResponse(**token_data)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar usuário (gestor)",
    description="Cria um novo usuário. **Apenas gestores** podem usar este endpoint. Permite definir roles (ex.: atendente, gestor). Requer token de gestor no header Authorization.",
    responses={
        201: {"description": "Usuário criado"},
        400: {"description": "E-mail já cadastrado"},
        401: {"description": "Não autenticado"},
        403: {"description": "Acesso negado (apenas gestor)"},
        422: {"description": "Dados de entrada inválidos"},
    },
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_manager: User = Depends(get_current_manager),
) -> UserResponse:
    auth_service = AuthService(db)
    
    # Register user (this will create user and assign roles if provided)
    token_data = auth_service.register_user(user_data)
    
    # Get the created user to return
    user_repo = auth_service.user_repo
    created_user = user_repo.get_by_email(user_data.email)
    
    if not created_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User was created but could not be retrieved",
        )
    
    return UserResponse.model_validate(created_user)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Usuário atual",
    description="Retorna os dados do usuário autenticado (a partir do token JWT). Requer Authorization: Bearer <token>.",
    responses={
        200: {"description": "Dados do usuário"},
        401: {"description": "Token inválido ou ausente"},
    },
)
def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post(
    "/public/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registro público",
    description="Cadastro aberto: qualquer um pode se registrar. O novo usuário recebe automaticamente a role **atendente**. Retorna o token JWT para login imediato. Roles podem ser alteradas depois por um gestor.",
    responses={
        201: {"description": "Usuário criado e token retornado"},
        400: {"description": "E-mail já cadastrado"},
        422: {"description": "Dados de entrada inválidos"},
    },
)
def public_register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
) -> TokenResponse:
    from fastapi import HTTPException
    
    auth_service = AuthService(db)
    
    # Force role to 'atendente' for public registrations
    # Create a copy of user_data with atendente role
    user_data_with_role = UserCreate(
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
        role_names=["atendente"],  # Always assign atendente role
    )
    
    # Register user (this will create user and assign atendente role)
    token_data = auth_service.register_user(user_data_with_role)
    
    return TokenResponse(**token_data)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Esqueci minha senha",
    description="Envia um e-mail com link para redefinir a senha, se o e-mail existir na base. Por segurança, a resposta é sempre a mesma (não revela se o e-mail existe).",
    responses={
        200: {"description": "Mensagem genérica (sempre igual)"},
        422: {"description": "E-mail inválido"},
    },
)
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    auth_service = AuthService(db)
    auth_service.request_password_reset(request.email)
    return ForgotPasswordResponse()


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Redefinir senha",
    description="Altera a senha usando o token recebido no link do e-mail (enviado por **Esqueci minha senha**).",
    responses={
        200: {"description": "Senha alterada com sucesso"},
        400: {"description": "Token inválido ou expirado"},
        422: {"description": "Dados inválidos (ex.: senha curta)"},
    },
)
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> ResetPasswordResponse:
    auth_service = AuthService(db)
    auth_service.reset_password(
        token=request.token,
        new_password=request.new_password,
    )
    return ResetPasswordResponse()


# Google OAuth routes
@router.get(
    "/google/login",
    summary="Login com Google",
    description="Redireciona o usuário para a tela de autorização do Google. Após aprovar, o usuário volta em **/auth/google/callback** e depois é redirecionado ao frontend com o token na URL.",
    responses={302: {"description": "Redirecionamento para Google"}},
)
async def google_login(
    db: Session = Depends(get_db),
) -> RedirectResponse:
    oauth_service = OAuthService(db)

    # Use redirect URI from settings (must match Google Cloud Console exactly)
    authorization_url, _ = await oauth_service.get_google_authorization_url()

    return RedirectResponse(url=authorization_url)


@router.get(
    "/google/callback",
    summary="Callback do Google OAuth",
    description="Chamado pelo Google após o login. Troca o `code` por token, cria/atualiza o usuário e redireciona para o frontend com o token no fragmento da URL (ex.: frontend/auth/google/callback#token=...).",
    responses={
        302: {"description": "Redirecionamento para o frontend com token"},
        400: {"description": "Code inválido ou erro no OAuth"},
    },
)
async def google_callback(
    code: str,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    from app.config.settings import get_settings
    
    settings = get_settings()
    oauth_service = OAuthService(db)
    
    try:
        # Process OAuth callback and get token
        token_response = await oauth_service.handle_google_callback(code=code, state=state)
        
        # Redirect to frontend with token in URL fragment
        # Using fragment (#) instead of query param for security (not sent to server)
        frontend_callback_url = f"{settings.frontend_url}/auth/google/callback#token={token_response.access_token}"
        
        return RedirectResponse(url=frontend_callback_url)
    except Exception as e:
        # Redirect to frontend with error
        from fastapi import HTTPException
        error_message = str(e) if isinstance(e, HTTPException) else "OAuth authentication failed"
        frontend_error_url = f"{settings.frontend_url}/auth/google/callback?error={error_message}"
        return RedirectResponse(url=frontend_error_url)

