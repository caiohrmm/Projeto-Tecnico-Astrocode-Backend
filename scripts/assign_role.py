"""Script to assign a role to an existing user."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db import SessionLocal
from app.users.repository import UserRepository
from app.users.role_repository import RoleRepository

VALID_ROLES = ["atendente", "corretor", "gestor"]


def assign_role(
    email: str,
    role_name: str,
) -> None:
    """
    Assign a role to an existing user.

    Args:
        email: User email
        role_name: Role name to assign
    """
    if role_name not in VALID_ROLES:
        print(f"[ERRO] Role invalida: {role_name}")
        print(f"   Roles validas: {VALID_ROLES}")
        return

    db = SessionLocal()

    try:
        user_repo = UserRepository(db)
        role_repo = RoleRepository(db)

        # Get user
        user = user_repo.get_by_email(email)
        if not user:
            print(f"[ERRO] Usuario com email '{email}' nao encontrado!")
            return

        # Get role
        role = role_repo.get_by_name(role_name)
        if not role:
            print(f"[ERRO] Role '{role_name}' nao encontrada no banco de dados!")
            print("   Execute as migrations primeiro: alembic upgrade head")
            return

        # Check if user already has this role
        current_role_names = [r.name for r in user.roles]
        if role_name in current_role_names:
            print(f"[INFO] Usuario ja possui a role '{role_name}'")
            print(f"   Roles atuais: {current_role_names}")
            return

        # Add role (keep existing roles)
        user.roles.append(role)
        db.commit()
        db.refresh(user)

        print(f"[OK] Role '{role_name}' atribuida com sucesso!")
        print(f"   Usuario: {user.email}")
        print(f"   Roles atuais: {[r.name for r in user.roles]}")

    except Exception as e:
        print(f"[ERRO] Erro ao atribuir role: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Atribuir role a um usuario existente")
    parser.add_argument("--email", required=True, help="Email do usuario")
    parser.add_argument("--role", required=True, choices=VALID_ROLES, help="Role a atribuir")

    args = parser.parse_args()

    assign_role(
        email=args.email,
        role_name=args.role,
    )

