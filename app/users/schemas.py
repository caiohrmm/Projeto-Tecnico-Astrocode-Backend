"""Pydantic schemas for user validation and serialization."""

import uuid
from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """Base schema with common user fields."""

    email: EmailStr = Field(..., description="E-mail do usuário")
    full_name: str = Field(..., min_length=1, max_length=255, description="Nome completo")


class UserCreate(UserBase):
    """
    Schema for creating a new user (usado no auth/registro, se aplicável).
    """

    password: str = Field(..., min_length=8, max_length=100, description="Senha em texto plano (será hasheada)")
    role_names: List[str] | None = Field(None, description="Roles a atribuir (ex.: atendente, corretor, gestor)")


class UserUpdate(BaseModel):
    """
    Schema for updating user information. All fields optional (atualização parcial).
    """

    email: EmailStr | None = Field(None, description="Novo e-mail")
    full_name: str | None = Field(None, min_length=1, max_length=255, description="Novo nome completo")
    is_active: bool | None = Field(None, description="Ativo/inativo (gestor não pode desativar a si mesmo)")


class UserResponse(UserBase):
    """
    Schema for user response (serialization). Não expõe senha.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID do usuário")
    is_active: bool = Field(..., description="Se o usuário está ativo")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Data da última atualização")
    roles: List["RoleResponse"] = Field(default_factory=list, description="Roles do usuário")


class UserInDB(UserResponse):
    """
    Schema for user stored in database.

    Includes hashed_password for internal use.
    """

    hashed_password: str


# Role schemas
class RoleBase(BaseModel):
    """Base schema with common role fields."""

    name: str = Field(..., min_length=1, max_length=100, description="Nome da role (ex.: atendente, corretor, gestor)")
    description: str | None = Field(None, max_length=500, description="Descrição da role")


class RoleCreate(RoleBase):
    """
    Schema for creating a new role.

    Attributes:
        name: Role name (must be unique)
        description: Optional role description
    """

    pass


class RoleUpdate(BaseModel):
    """Schema for updating role information. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=100, description="Nome da role")
    description: str | None = Field(None, max_length=500, description="Descrição")


class RoleResponse(RoleBase):
    """Schema for role response (serialization)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID da role")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Data da última atualização")

