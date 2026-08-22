"""Cria o primeiro usuário (admin) do sistema.

O cadastro normal (/auth/register) exige um código de indicação de um
usuário já existente — igual ao app desktop. Isso trava o "usuário zero":
não há ninguém ainda para indicar o primeiro cadastro. Este script contorna
essa trava só para o bootstrap inicial (bypass_referral_validation=True),
igual ao parâmetro equivalente que já existia em
crud/sqlalchemy_user_manager.py no projeto original.

Uso:
    cd backend
    python -m scripts.create_admin
"""
import getpass
import sys

from app.crud import user as user_crud
from app.db.session import SessionLocal


def main() -> None:
    print("=== Nuvion Web — criar usuário admin inicial ===")
    username = input("Username: ").strip()
    email = input("Email: ").strip()
    name = input("Nome completo: ").strip()
    phone = input("Telefone (com DDD): ").strip()
    password = getpass.getpass("Senha (mín. 8 caracteres, maiúscula+minúscula+número): ")

    db = SessionLocal()
    try:
        ok, result = user_crud.register_user(
            db,
            username=username,
            password=password,
            email=email,
            name=name,
            phone=phone,
            account_type="Admin",
            status="Ativo",
            bypass_referral_validation=True,
        )
    finally:
        db.close()

    if not ok:
        print(f"Erro: {result}")
        sys.exit(1)

    print(f"Usuário admin criado com sucesso — id={result}")


if __name__ == "__main__":
    main()
