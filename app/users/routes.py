"""User management routes (for managers only)."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, get_current_manager
from app.db import get_db
from app.users.models import User
from app.users.repository import UserRepository
from app.users.role_repository import RoleRepository
from app.users.schemas import UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.put(
    "/{user_id}/roles",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar roles do usuário",
    description="""
Atribui ou altera as roles de um usuário. Apenas **gestores** podem executar.

**Roles válidas:** `atendente`, `corretor`, `gestor`. O body é uma lista de strings (ex.: `["atendente", "corretor"]`). Todas as roles informadas devem existir no banco; nomes inválidos ou inexistentes retornam 400.

Requer autenticação (gestor).
    """.strip(),
    responses={
        200: {"description": "Usuário atualizado com novas roles"},
        400: {"description": "Roles inválidas ou não encontradas no banco"},
        401: {"description": "Não autenticado"},
        403: {"description": "Sem permissão (requer gestor)"},
        404: {"description": "Usuário não encontrado"},
        422: {"description": "Payload inválido"},
    },
)
def update_user_roles(
    user_id: uuid.UUID,
    role_names: List[str],
    db: Session = Depends(get_db),
    current_manager: User = Depends(get_current_manager),
) -> UserResponse:
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)

    # Get user to update
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Validate role names
    valid_roles = ["atendente", "corretor", "gestor"]
    invalid_roles = [role for role in role_names if role not in valid_roles]
    if invalid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role names: {invalid_roles}. Valid roles are: {valid_roles}",
        )

    # Check if all roles exist in database
    existing_roles = role_repo.get_by_names(role_names)
    existing_role_names = [role.name for role in existing_roles]
    missing_roles = [role for role in role_names if role not in existing_role_names]
    if missing_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Roles not found in database: {missing_roles}",
        )

    # Update user roles
    updated_user = user_repo.assign_roles(user, role_names)

    return UserResponse.model_validate(updated_user)


@router.get(
    "/",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar usuários",
    description="""
Lista todos os usuários com paginação. Apenas **gestores** podem acessar.

Requer autenticação (gestor).
    """.strip(),
    responses={
        200: {"description": "Lista de usuários"},
        401: {"description": "Não autenticado"},
        403: {"description": "Sem permissão (requer gestor)"},
    },
)
def list_users(
    skip: int = Query(0, ge=0, description="Registros a pular (paginação)"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros"),
    db: Session = Depends(get_db),
    current_manager: User = Depends(get_current_manager),
) -> List[UserResponse]:
    user_repo = UserRepository(db)
    users = user_repo.get_all(skip=skip, limit=limit)
    return [UserResponse.model_validate(user) for user in users]


@router.get(
    "/corretores",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar corretores",
    description="""
Lista usuários com role **corretor** que estão ativos. Qualquer usuário autenticado pode acessar (não só gestores), para uso em seleção de agente em atendimentos, imóveis, visitas, etc.

Requer autenticação.
    """.strip(),
    responses={
        200: {"description": "Lista de corretores ativos"},
        401: {"description": "Não autenticado"},
    },
)
def list_corretores(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> List[UserResponse]:
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)
    
    # Get 'corretor' role
    corretor_role = role_repo.get_by_name("corretor")
    if not corretor_role:
        return []
    
    # Get all users with 'corretor' role
    users = user_repo.get_by_role(corretor_role.id)
    
    # Filter only active users
    active_users = [user for user in users if user.is_active]
    
    return [UserResponse.model_validate(user) for user in active_users]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Buscar usuário por ID",
    description="Retorna um usuário pelo UUID. Apenas **gestores** podem acessar. Inclui e-mail, nome, is_active, roles e timestamps.",
    responses={
        200: {"description": "Usuário encontrado"},
        401: {"description": "Não autenticado"},
        403: {"description": "Sem permissão (requer gestor)"},
        404: {"description": "Usuário não encontrado"},
    },
)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_manager: User = Depends(get_current_manager),
) -> UserResponse:
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualizar usuário",
    description="""
Atualização parcial de usuário (e-mail, nome completo, is_active). Apenas **gestores** podem executar.

**Regra:** o gestor não pode desativar a si mesmo (is_active = false no próprio usuário retorna 400).

Requer autenticação (gestor).
    """.strip(),
    responses={
        200: {"description": "Usuário atualizado"},
        400: {"description": "Tentativa de desativar a própria conta"},
        401: {"description": "Não autenticado"},
        403: {"description": "Sem permissão (requer gestor)"},
        404: {"description": "Usuário não encontrado"},
        422: {"description": "Dados inválidos"},
    },
)
def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_manager: User = Depends(get_current_manager),
) -> UserResponse:
    user_repo = UserRepository(db)

    # Get user to update
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent manager from deactivating themselves
    if user_data.is_active is False and user.id == current_manager.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    # Update user
    updated_user = user_repo.update(user, user_data)

    return UserResponse.model_validate(updated_user)

