"""Testes de configurações de navegação (anti-detecção) por usuário — Fase 2.
Usa as fixtures `client`/`db_session` de conftest.py."""
from app.crud import user as user_crud


def _auth_headers(client, db_session, username: str = "configdono") -> dict:
    db = db_session()
    try:
        ok, _ = user_crud.register_user(
            db,
            username=username,
            password="SenhaForte123",
            email=f"{username}@nuvion.dev",
            name="Dono de Config",
            phone="11944443333",
            account_type="Membro",
            status="Ativo",
            bypass_referral_validation=True,
        )
        assert ok
    finally:
        db.close()

    login = client.post(
        "/auth/login", json={"username_or_email": username, "password": "SenhaForte123"}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_browser_settings_require_auth(client):
    response = client.get("/browser-settings/me")
    assert response.status_code == 401


def test_get_creates_defaults_on_first_access(client, db_session):
    headers = _auth_headers(client, db_session)
    response = client.get("/browser-settings/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["theme"] == "dark"
    assert body["language"] == "pt_BR"
    assert body["anti_detection_settings"]["spoof_webdriver"] is True

    # Segunda chamada deve reutilizar a mesma linha, não criar outra.
    second = client.get("/browser-settings/me", headers=headers)
    assert second.json()["id"] == body["id"]


def test_update_browser_settings(client, db_session):
    headers = _auth_headers(client, db_session)
    client.get("/browser-settings/me", headers=headers)

    response = client.patch(
        "/browser-settings/me",
        json={"theme": "light", "anti_detection_settings": {"spoof_webdriver": False}},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["theme"] == "light"
    assert body["anti_detection_settings"] == {"spoof_webdriver": False}
