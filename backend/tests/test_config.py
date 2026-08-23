"""Testes de app/core/config.py — hoje só o parsing tolerante de
CORS_ALLOWED_ORIGINS (ver o comentário no validador em app/core/config.py
sobre por que isso existe: JSON estrito via variável de ambiente de um
painel tipo EasyPanel é uma fonte comum de erro de deploy)."""
from app.core.config import Settings

_REQUIRED = {
    "DB_USER": "user",
    "DB_PASSWORD": "pass",
    "JWT_SECRET_KEY": "jwt-secret",
    "ENCRYPTION_KEY": "ASwOOLlSPXQ02i9TupC7AX-ESN5u-CR5gW6uzGXHN0Q=",
}


def _settings(cors_value):
    return Settings(CORS_ALLOWED_ORIGINS=cors_value, **_REQUIRED)


def test_cors_accepts_valid_json_array():
    assert _settings('["https://app.exemplo.com"]').CORS_ALLOWED_ORIGINS == [
        "https://app.exemplo.com"
    ]


def test_cors_accepts_bare_url_without_brackets():
    assert _settings("https://app.exemplo.com").CORS_ALLOWED_ORIGINS == [
        "https://app.exemplo.com"
    ]


def test_cors_accepts_comma_separated_list():
    assert _settings("https://a.com,http://localhost:3000").CORS_ALLOWED_ORIGINS == [
        "https://a.com",
        "http://localhost:3000",
    ]


def test_cors_accepts_json_with_single_quotes_malformed():
    # Erro comum ao digitar numa caixa de texto de env var — aspas simples
    # em vez de duplas não é JSON válido, mas não deve derrubar o backend.
    assert _settings("['https://a.com', 'https://b.com']").CORS_ALLOWED_ORIGINS == [
        "https://a.com",
        "https://b.com",
    ]


def test_cors_strips_stray_quotes_without_brackets():
    assert _settings('"https://a.com","https://b.com"').CORS_ALLOWED_ORIGINS == [
        "https://a.com",
        "https://b.com",
    ]


def test_cors_empty_string_is_empty_list():
    assert _settings("").CORS_ALLOWED_ORIGINS == []


def test_cors_already_a_list_passes_through():
    assert _settings(["https://a.com"]).CORS_ALLOWED_ORIGINS == ["https://a.com"]


def test_cors_default_is_localhost_only():
    settings = Settings(**_REQUIRED)
    assert settings.CORS_ALLOWED_ORIGINS == ["http://localhost:3000"]
