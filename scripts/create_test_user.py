"""Script to create a test user for authentication testing."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.auth.password import hash_password
from app.config.settings import get_settings
from app.db import SessionLocal
from app.users.repository import UserRepository
from app.users.schemas import UserCreate

settings = get_settings()


def create_test_user(
    email: str = "test@example.com",
    password: str = "senha123456",
    full_name: str = "Usuário Teste",
) -> None:
    """
    Create a test user in the database.

    Args:
        email: User email
        password: User password
        full_name: User full name
    """
    db = SessionLocal()

    try:
        user_repo = UserRepository(db)

        # Check if user already exists
        existing_user = user_repo.get_by_email(email)
        if existing_user:
            print(f"[ERRO] Usuario com email '{email}' ja existe!")
            print(f"   ID: {existing_user.id}")
            return

        # Create user
        user_data = UserCreate(
            email=email,
            password=password,
            full_name=full_name,
        )

        hashed = hash_password(user_data.password)
        user = user_repo.create(user_data, hashed)

        print("[OK] Usuario criado com sucesso!")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Nome: {user.full_name}")
        print(f"\nCredenciais para login:")
        print(f"   Email: {email}")
        print(f"   Senha: {password}")

    except Exception as e:
        print(f"[ERRO] Erro ao criar usuario: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Criar usuário de teste")
    parser.add_argument("--email", default="test@example.com", help="Email do usuário")
    parser.add_argument("--password", default="senha123456", help="Senha do usuário")
    parser.add_argument("--name", default="Usuário Teste", help="Nome completo")

    args = parser.parse_args()

    create_test_user(
        email=args.email,
        password=args.password,
        full_name=args.name,
    )

