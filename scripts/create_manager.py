"""Script to create the first manager (gestor) user."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.auth.password import hash_password
from app.config.settings import get_settings
from app.db import SessionLocal
from app.users.repository import UserRepository
from app.users.role_repository import RoleRepository
from app.users.schemas import UserCreate

settings = get_settings()


def create_manager(
    email: str = "gestor@example.com",
    password: str = "senha123456",
    full_name: str = "Gestor Principal",
) -> None:
    """
    Create the first manager (gestor) user.

    Args:
        email: Manager email
        password: Manager password
        full_name: Manager full name
    """
    db = SessionLocal()

    try:
        user_repo = UserRepository(db)
        role_repo = RoleRepository(db)

        # Check if user already exists
        existing_user = user_repo.get_by_email(email)
        if existing_user:
            print(f"[ERRO] Usuario com email '{email}' ja existe!")
            print(f"   ID: {existing_user.id}")
            print(f"\nPara atribuir role 'gestor' a este usuario, execute:")
            print(f"   python scripts/assign_role.py --email {email} --role gestor")
            return

        # Create user
        user_data = UserCreate(
            email=email,
            password=password,
            full_name=full_name,
        )

        hashed = hash_password(user_data.password)
        user = user_repo.create(user_data, hashed)

        # Get gestor role
        gestor_role = role_repo.get_by_name("gestor")
        if not gestor_role:
            print("[ERRO] Role 'gestor' nao encontrada no banco de dados!")
            print("   Execute as migrations primeiro: alembic upgrade head")
            return

        # Assign gestor role
        user.roles = [gestor_role]
        db.commit()
        db.refresh(user)

        print("[OK] Gestor criado com sucesso!")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Nome: {user.full_name}")
        print(f"   Roles: {[r.name for r in user.roles]}")
        print(f"\nCredenciais para login:")
        print(f"   Email: {email}")
        print(f"   Senha: {password}")
        print(f"\nAgora voce pode usar este usuario para criar outros usuarios via API!")

    except Exception as e:
        print(f"[ERRO] Erro ao criar gestor: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Criar primeiro gestor do sistema")
    parser.add_argument("--email", default="gestor@example.com", help="Email do gestor")
    parser.add_argument("--password", default="senha123456", help="Senha do gestor")
    parser.add_argument("--name", default="Gestor Principal", help="Nome completo")

    args = parser.parse_args()

    create_manager(
        email=args.email,
        password=args.password,
        full_name=args.name,
    )

