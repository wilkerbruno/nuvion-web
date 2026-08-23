"""Testes de `GET /ai-tools/{id}/launch` (Fase 5) — o endpoint que reúne
tudo que a extensão precisa para abrir uma ferramenta já roteada pelo proxy
atribuído pelo admin e já logada (cookies ou credenciais diretas)."""
import hashlib

from app.crud import user as user_crud


def _phone_for(username: str) -> str:
    digest = hashlib.md5(username.encode()).hexdigest()
    digits = "".join(str(int(ch, 16) % 10) for ch in digest[:8])
    return ("119" + digits)[:11]


def _register_and_login(client, db_session, username: str, account_type: str = "Membro") -> dict:
    db = db_session()
    try:
        ok, _ = user_crud.register_user(
            db,
            username=username,
            password="SenhaForte123",
            email=f"{username}@nuvion.dev",
            name="Usuário de Teste",
            phone=_phone_for(username),
            account_type=account_type,
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


def _admin_headers(client, db_session, username: str = "adminlaunch") -> dict:
    return _register_and_login(client, db_session, username, account_type="Admin")


def _create_tool(client, admin_headers, **overrides) -> dict:
    payload = {
        "name": overrides.pop("name", "Ferramenta Launch"),
        "url": "https://ferramenta.example.com/app",
        "login_method": "manual",
    }
    payload.update(overrides)
    response = client.post("/ai-tools", json=payload, headers=admin_headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_launch_requires_auth(client):
    assert client.get("/ai-tools/qualquer-id/launch").status_code == 401


def test_launch_404_for_unknown_tool(client, db_session):
    headers = _register_and_login(client, db_session, "userlaunch404")
    response = client.get("/ai-tools/nao-existe/launch", headers=headers)
    assert response.status_code == 404


def test_launch_minimal_tool_has_no_proxy_credentials_or_cookies(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminlaunchmin")
    tool = _create_tool(client, admin_headers, name="Ferramenta Minima")

    user_headers = _register_and_login(client, db_session, "userlaunchmin")
    response = client.get(f"/ai-tools/{tool['id']}/launch", headers=user_headers)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["ai_tool_id"] == tool["id"]
    assert body["url"] == "https://ferramenta.example.com/app"
    assert body["login_method"] == "manual"
    assert body["proxy"] is None
    assert body["credentials"] is None
    assert body["cookies"] is None


def test_launch_returns_proxy_connection_info_when_assigned(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminlaunchproxy")

    proxy_response = client.post(
        "/admin/proxies",
        json={
            "name": "Proxy da Ferramenta",
            "host": "10.0.0.9",
            "port": 8080,
            "proxy_type": "HTTP",
            "username": "proxyuser",
            "password": "proxypass",
        },
        headers=admin_headers,
    )
    assert proxy_response.status_code == 201, proxy_response.text
    proxy = proxy_response.json()

    tool = _create_tool(client, admin_headers, name="Ferramenta Com Proxy", proxy_id=proxy["id"])

    user_headers = _register_and_login(client, db_session, "userlaunchproxy")
    response = client.get(f"/ai-tools/{tool['id']}/launch", headers=user_headers)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["proxy"] == {
        "host": "10.0.0.9",
        "port": 8080,
        "proxy_type": "HTTP",
        "username": "proxyuser",
        "password": "proxypass",
    }


def test_launch_returns_decrypted_credentials_when_configured(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminlaunchcreds")
    tool = _create_tool(
        client, admin_headers, name="Ferramenta Com Credenciais", login_method="credentials"
    )

    set_response = client.put(
        f"/ai-tools/{tool['id']}/credentials",
        json={
            "username": "usuario@ferramenta.com",
            "password": "SenhaSecreta123",
            "login_url": "https://ferramenta.example.com/login",
        },
        headers=admin_headers,
    )
    assert set_response.status_code == 200, set_response.text

    user_headers = _register_and_login(client, db_session, "userlaunchcreds")
    response = client.get(f"/ai-tools/{tool['id']}/launch", headers=user_headers)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["login_method"] == "credentials"
    assert body["credentials"]["username"] == "usuario@ferramenta.com"
    assert body["credentials"]["password"] == "SenhaSecreta123"
    assert body["credentials"]["login_url"] == "https://ferramenta.example.com/login"


def test_launch_returns_cookies_when_configured(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminlaunchcookies")
    tool = _create_tool(
        client, admin_headers, name="Ferramenta Com Cookies", login_method="cookies"
    )

    set_response = client.put(
        f"/ai-tools/{tool['id']}/cookies",
        json={
            "cookies_data": [
                {"name": "session", "value": "abc123", "domain": "ferramenta.example.com"}
            ]
        },
        headers=admin_headers,
    )
    assert set_response.status_code == 200, set_response.text

    user_headers = _register_and_login(client, db_session, "userlaunchcookies")
    response = client.get(f"/ai-tools/{tool['id']}/launch", headers=user_headers)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["login_method"] == "cookies"
    assert body["cookies"] == [
        {"name": "session", "value": "abc123", "domain": "ferramenta.example.com"}
    ]
