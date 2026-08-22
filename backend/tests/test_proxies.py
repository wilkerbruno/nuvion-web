"""Testes de CRUD de proxy por usuário (Fase 2). Usa as fixtures
`client`/`db_session` de conftest.py — SQLite em memória, sem MySQL real."""
from app.crud import user as user_crud


def _phone_for(username: str) -> str:
    # Telefone único e determinístico por usuário de teste (evita colisão de
    # UNIQUE constraint quando um teste cria mais de um usuário).
    digits = "".join(str((ord(c) + i) % 10) for i, c in enumerate(username))
    return ("119" + digits + "0000000")[:11]


def _auth_headers(client, db_session, username: str = "proxydono") -> dict:
    db = db_session()
    try:
        ok, _ = user_crud.register_user(
            db,
            username=username,
            password="SenhaForte123",
            email=f"{username}@nuvion.dev",
            name="Dono de Proxy",
            phone=_phone_for(username),
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


def _create_proxy(client, headers: dict, name: str = "Proxy 1", port: int = 8080) -> dict:
    response = client.post(
        "/proxies",
        json={
            "name": name,
            "host": "192.168.0.10",
            "port": port,
            "proxy_type": "HTTP",
            "username": "proxyuser",
            "password": "proxypass",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_proxies_require_auth(client):
    response = client.get("/proxies")
    assert response.status_code == 401


def test_create_and_list_proxies(client, db_session):
    headers = _auth_headers(client, db_session)
    created = _create_proxy(client, headers)
    assert created["is_selected"] is False
    assert created["password"] == "proxypass"

    listing = client.get("/proxies", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["id"] == created["id"]


def test_proxies_are_scoped_per_user(client, db_session):
    headers_a = _auth_headers(client, db_session, "usuarioa")
    headers_b = _auth_headers(client, db_session, "usuariob")
    _create_proxy(client, headers_a, name="Proxy da A")

    listing_b = client.get("/proxies", headers=headers_b)
    assert listing_b.status_code == 200
    assert listing_b.json() == []


def test_select_active_proxy_unselects_others(client, db_session):
    headers = _auth_headers(client, db_session)
    proxy_1 = _create_proxy(client, headers, name="Proxy 1", port=8001)
    proxy_2 = _create_proxy(client, headers, name="Proxy 2", port=8002)

    select_1 = client.post(f"/proxies/{proxy_1['id']}/select", headers=headers)
    assert select_1.status_code == 200
    assert select_1.json()["is_selected"] is True

    select_2 = client.post(f"/proxies/{proxy_2['id']}/select", headers=headers)
    assert select_2.status_code == 200
    assert select_2.json()["is_selected"] is True

    listing = {p["id"]: p for p in client.get("/proxies", headers=headers).json()}
    assert listing[proxy_1["id"]]["is_selected"] is False
    assert listing[proxy_2["id"]]["is_selected"] is True

    active = client.get("/proxies/active", headers=headers)
    assert active.status_code == 200
    assert active.json()["id"] == proxy_2["id"]


def test_active_proxy_404_when_none_selected(client, db_session):
    headers = _auth_headers(client, db_session)
    response = client.get("/proxies/active", headers=headers)
    assert response.status_code == 404


def test_cannot_select_or_delete_another_users_proxy(client, db_session):
    headers_a = _auth_headers(client, db_session, "usuarioc")
    headers_b = _auth_headers(client, db_session, "usuariod")
    proxy_a = _create_proxy(client, headers_a)

    select_attempt = client.post(f"/proxies/{proxy_a['id']}/select", headers=headers_b)
    assert select_attempt.status_code == 404

    delete_attempt = client.delete(f"/proxies/{proxy_a['id']}", headers=headers_b)
    assert delete_attempt.status_code == 404


def test_update_and_delete_proxy(client, db_session):
    headers = _auth_headers(client, db_session)
    proxy = _create_proxy(client, headers)

    update_response = client.patch(
        f"/proxies/{proxy['id']}", json={"name": "Proxy Renomeado"}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Proxy Renomeado"

    delete_response = client.delete(f"/proxies/{proxy['id']}", headers=headers)
    assert delete_response.status_code == 204

    listing = client.get("/proxies", headers=headers)
    assert listing.json() == []
