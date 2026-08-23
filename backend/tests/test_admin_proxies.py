"""Testes do CRUD de admin de proxies globais/compartilhados (`/admin/proxies`,
ver app/api/routes/admin_proxies.py) — diferente de `/proxies` (proxy pessoal
de cada usuário, ver tests/test_proxies.py). Estes são os proxies que um
admin atribui a uma ferramenta de IA via `AITool.proxy_id`."""
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


def _admin_headers(client, db_session, username: str = "adminproxyglobal") -> dict:
    return _register_and_login(client, db_session, username, account_type="Admin")


def _create_global_proxy(client, admin_headers, name: str = "Proxy Global 1", port: int = 9001) -> dict:
    response = client.post(
        "/admin/proxies",
        json={"name": name, "host": "10.0.0.1", "port": port, "proxy_type": "HTTP"},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_admin_proxies_requires_auth(client):
    assert client.get("/admin/proxies").status_code == 401


def test_only_admin_can_manage_global_proxies(client, db_session):
    user_headers = _register_and_login(client, db_session, "usuariocomumpx")

    assert client.get("/admin/proxies", headers=user_headers).status_code == 403
    assert (
        client.post(
            "/admin/proxies",
            json={"name": "X", "host": "1.2.3.4", "port": 80, "proxy_type": "HTTP"},
            headers=user_headers,
        ).status_code
        == 403
    )


def test_admin_creates_lists_updates_and_deletes_global_proxy(client, db_session):
    admin_headers = _admin_headers(client, db_session, "admincrudpx")

    created = _create_global_proxy(client, admin_headers)
    assert created["name"] == "Proxy Global 1"

    listing = client.get("/admin/proxies", headers=admin_headers)
    assert listing.status_code == 200
    assert any(p["id"] == created["id"] for p in listing.json())

    updated = client.patch(
        f"/admin/proxies/{created['id']}", json={"name": "Renomeado"}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renomeado"

    deleted = client.delete(f"/admin/proxies/{created['id']}", headers=admin_headers)
    assert deleted.status_code == 204

    after_delete = client.get("/admin/proxies", headers=admin_headers)
    assert all(p["id"] != created["id"] for p in after_delete.json())


def test_global_proxies_are_isolated_from_personal_proxies(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminisoladopx")
    user_headers = _register_and_login(client, db_session, "usuariopessoalpx")

    _create_global_proxy(client, admin_headers, name="Global Isolado")
    personal = client.post(
        "/proxies",
        json={"name": "Pessoal", "host": "192.168.0.1", "port": 8080, "proxy_type": "HTTP"},
        headers=user_headers,
    )
    assert personal.status_code == 201

    # O proxy pessoal do usuário não aparece na lista de proxies globais...
    global_listing = client.get("/admin/proxies", headers=admin_headers).json()
    assert all(p["name"] != "Pessoal" for p in global_listing)

    # ...e o proxy global do admin não aparece na lista pessoal do usuário.
    personal_listing = client.get("/proxies", headers=user_headers).json()
    assert all(p["name"] != "Global Isolado" for p in personal_listing)


def test_update_and_delete_unknown_global_proxy_404(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminnaoexistepx")

    assert (
        client.patch(
            "/admin/proxies/nao-existe", json={"name": "X"}, headers=admin_headers
        ).status_code
        == 404
    )
    assert client.delete("/admin/proxies/nao-existe", headers=admin_headers).status_code == 404


def test_ai_tool_can_be_assigned_a_global_proxy(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminvinculopx")
    proxy = _create_global_proxy(client, admin_headers, name="Proxy da Ferramenta")

    tool = client.post(
        "/ai-tools",
        json={"name": "FerramentaComProxy", "url": "https://exemplo.dev", "proxy_id": proxy["id"]},
        headers=admin_headers,
    )
    assert tool.status_code == 201, tool.text
    assert tool.json()["proxy_id"] == proxy["id"]
