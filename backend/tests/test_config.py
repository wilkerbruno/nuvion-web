"""Testes de app/core/config.py — hoje só o parsing tolerante de
CORS_ALLOWED_ORIGINS (ver o comentário no campo/validador em
app/core/config.py sobre por que isso existe: JSON estrito via variável de
ambiente de um painel tipo EasyPanel é uma fonte comum de erro de deploy).

IMPORTANTE: os testes passam o valor via variável de ambiente de verdade
(monkeypatch.setenv), não via `Settings(CORS_ALLOWED_ORIGINS=...)` — passar
por kwarg do construtor usa uma fonte diferente (`init_kwargs`) que NÃO
passa pelo pré-parse de JSON que o pydantic-settings faz para campos
"complexos" (como List[str]) vindos de variável de ambiente
(`EnvSettingsSource`). Um teste só com kwarg passaria mesmo se o campo não
tivesse `NoDecode` — e foi exatamente esse o bug que escapou da primeira
versão deste arquivo: o validador funcionava via kwarg, mas o
pydantic-settings ainda derrubava a aplicação de verdade (`SettingsError`)
antes de chamar o validador, porque faltava `Annotated[..., NoDecode]` no
campo.
"""
from app.core.config import Settings

_REQUIRED_ENV = {
    "DB_USER": "user",
    "DB_PASSWORD": "pass",
    "JWT_SECRET_KEY": "jwt-secret",
    "ENCRYPTION_KEY": "ASwOOLlSPXQ02i9TupC7AX-ESN5u-CR5gW6uzGXHN0Q=",
}


def _settings_from_env(monkeypatch, cors_value=None):
    for key, value in _REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    if cors_value is None:
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", cors_value)
    return Settings()


def test_cors_accepts_valid_json_array(monkeypatch):
    settings = _settings_from_env(monkeypatch, '["https://app.exemplo.com"]')
    assert settings.CORS_ALLOWED_ORIGINS == ["https://app.exemplo.com"]


def test_cors_accepts_bare_url_without_brackets(monkeypatch):
    settings = _settings_from_env(monkeypatch, "https://app.exemplo.com")
    assert settings.CORS_ALLOWED_ORIGINS == ["https://app.exemplo.com"]


def test_cors_accepts_comma_separated_list(monkeypatch):
    settings = _settings_from_env(monkeypatch, "https://a.com,http://localhost:3000")
    assert settings.CORS_ALLOWED_ORIGINS == ["https://a.com", "http://localhost:3000"]


def test_cors_accepts_json_with_single_quotes_malformed(monkeypatch):
    # Erro comum ao digitar numa caixa de texto de env var — aspas simples
    # em vez de duplas não é JSON válido, mas não deve derrubar o backend.
    settings = _settings_from_env(monkeypatch, "['https://a.com', 'https://b.com']")
    assert settings.CORS_ALLOWED_ORIGINS == ["https://a.com", "https://b.com"]


def test_cors_strips_stray_quotes_without_brackets(monkeypatch):
    settings = _settings_from_env(monkeypatch, '"https://a.com","https://b.com"')
    assert settings.CORS_ALLOWED_ORIGINS == ["https://a.com", "https://b.com"]


def test_cors_empty_string_is_empty_list(monkeypatch):
    settings = _settings_from_env(monkeypatch, "")
    assert settings.CORS_ALLOWED_ORIGINS == []


def test_cors_default_is_localhost_only(monkeypatch):
    settings = _settings_from_env(monkeypatch)
    assert settings.CORS_ALLOWED_ORIGINS == ["http://localhost:3000"]
