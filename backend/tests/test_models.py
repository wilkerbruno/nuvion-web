"""Testes de sanidade dos modelos portados: garante que todas as tabelas do
projeto desktop original continuam registradas depois da migração."""
from app.models import Base

EXPECTED_TABLES = {
    "users", "ai_tools", "ai_direct_credentials", "ai_sessions",
    "ai_sessions_cookies", "user_favorites", "payments", "payment_configs",
    "browser_settings", "user_sessions", "downloads", "proxy",
    "device_data", "notifications", "expenses",
}


def test_all_expected_tables_are_registered():
    registered = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - registered
    assert not missing, f"Tabelas do sistema original ausentes na migração: {missing}"


def test_user_password_hash_roundtrip():
    from app.models.user import User

    user = User(
        username="teste", email="teste@nuvion.dev", name="Teste",
        phone="11999999999", referral_code="ABC123",
    )
    user.set_password("SenhaForte123")
    assert user.verify_password("SenhaForte123") is True
    assert user.verify_password("senha-errada") is False
