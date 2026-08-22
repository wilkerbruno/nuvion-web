"""Testes do catálogo de ferramentas de IA, favoritos, credenciais diretas
e cookies de sessão (Fase 4)."""
import hashlib

from app.crud import user as user_crud


def _phone_for(username: str) -> str:
    # Hash do username inteiro (não só um prefixo) para telefone único e
    # determinístico por teste — evita colisão de UNIQUE constraint entre
    # usernames que compartilham prefixo (ex.: "indicado2"/"indicador2").
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


def _admin_headers(client, db_session, username: str = "adminia") -> dict:
    return _register_and_login(client, db_session, username, account_type="Admin")


def _create_tool(client, admin_headers, name: str = "ChatIA") -> dict:
    response = client.post(
        "/ai-tools",
        json={"name": name, "url": "https://exemplo.dev", "category": "conversacao", "tags": ["IA"]},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_list_tools_requires_auth(client):
    assert client.get("/ai-tools").status_code == 401


def test_only_admin_can_create_tool(client, db_session):
    user_headers = _register_and_login(client, db_session, "usuariocomum")
    response = client.post(
        "/ai-tools", json={"name": "X", "url": "https://x.dev"}, headers=user_headers
    )
    assert response.status_code == 403


def test_admin_creates_and_user_lists_tool(client, db_session):
    admin_headers = _admin_headers(client, db_session)
    tool = _create_tool(client, admin_headers)

    user_headers = _register_and_login(client, db_session, "listador")
    listing = client.get("/ai-tools", headers=user_headers)
    assert listing.status_code == 200
    assert any(t["id"] == tool["id"] for t in listing.json())
    assert listing.json()[0]["is_favorite"] is False


def test_cannot_create_duplicate_tool_name(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminduplicado")
    _create_tool(client, admin_headers, name="Único")

    dup = client.post(
        "/ai-tools", json={"name": "Único", "url": "https://outro.dev"}, headers=admin_headers
    )
    assert dup.status_code == 400


def test_favorite_toggle(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminfav")
    tool = _create_tool(client, admin_headers, name="FavIA")
    user_headers = _register_and_login(client, db_session, "userfav")

    toggle_on = client.post(f"/ai-tools/{tool['id']}/favorite", headers=user_headers)
    assert toggle_on.status_code == 200
    assert toggle_on.json()["is_favorite"] is True

    favorites = client.get("/ai-tools/favorites", headers=user_headers)
    assert favorites.status_code == 200
    assert len(favorites.json()) == 1
    assert favorites.json()[0]["id"] == tool["id"]

    toggle_off = client.post(f"/ai-tools/{tool['id']}/favorite", headers=user_headers)
    assert toggle_off.status_code == 200
    assert toggle_off.json()["is_favorite"] is False

    favorites_after = client.get("/ai-tools/favorites", headers=user_headers)
    assert favorites_after.json() == []


def test_update_and_delete_tool_admin_only(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminupdate")
    user_headers = _register_and_login(client, db_session, "naoadmin")
    tool = _create_tool(client, admin_headers, name="Editável")

    forbidden = client.patch(
        f"/ai-tools/{tool['id']}", json={"is_featured": True}, headers=user_headers
    )
    assert forbidden.status_code == 403

    updated = client.patch(
        f"/ai-tools/{tool['id']}", json={"is_featured": True}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["is_featured"] is True

    delete_forbidden = client.delete(f"/ai-tools/{tool['id']}", headers=user_headers)
    assert delete_forbidden.status_code == 403

    delete_ok = client.delete(f"/ai-tools/{tool['id']}", headers=admin_headers)
    assert delete_ok.status_code == 204


def test_direct_credentials_never_leak_password(client, db_session):
    admin_headers = _admin_headers(client, db_session, "admincred")
    tool = _create_tool(client, admin_headers, name="CredIA")
    user_headers = _register_and_login(client, db_session, "usercred")

    empty_summary = client.get(f"/ai-tools/{tool['id']}/credentials", headers=user_headers)
    assert empty_summary.status_code == 200
    assert empty_summary.json()["configured"] is False

    forbidden = client.put(
        f"/ai-tools/{tool['id']}/credentials",
        json={"username": "bot@exemplo.dev", "password": "SegredoSuperSecreto123"},
        headers=user_headers,
    )
    assert forbidden.status_code == 403

    set_response = client.put(
        f"/ai-tools/{tool['id']}/credentials",
        json={"username": "bot@exemplo.dev", "password": "SegredoSuperSecreto123"},
        headers=admin_headers,
    )
    assert set_response.status_code == 200
    assert set_response.json()["configured"] is True
    assert "password" not in set_response.text
    assert "SegredoSuperSecreto123" not in set_response.text

    read_back = client.get(f"/ai-tools/{tool['id']}/credentials", headers=user_headers)
    assert read_back.status_code == 200
    assert read_back.json()["configured"] is True
    assert "SegredoSuperSecreto123" not in read_back.text

    # A senha cifrada no banco não pode ser igual à senha em texto puro.
    from app.crud import ai_direct_credentials as credentials_crud

    db = db_session()
    try:
        stored = credentials_crud.get_by_ai_tool(db, tool["id"])
        assert stored.password != "SegredoSuperSecreto123"
        assert credentials_crud.get_decrypted_password(stored) == "SegredoSuperSecreto123"
    finally:
        db.close()

    delete_response = client.delete(f"/ai-tools/{tool['id']}/credentials", headers=admin_headers)
    assert delete_response.status_code == 204


def test_cookie_session_summary_and_delete(client, db_session):
    admin_headers = _admin_headers(client, db_session, "admincookie")
    tool = _create_tool(client, admin_headers, name="CookieIA")

    cookies_payload = {
        "cookies_data": [
            {"name": "session_id", "value": "abc123", "domain": ".exemplo.dev"},
            {"name": "auth_token", "value": "xyz789", "domain": ".exemplo.dev"},
        ]
    }
    set_response = client.put(
        f"/ai-tools/{tool['id']}/cookies", json=cookies_payload, headers=admin_headers
    )
    assert set_response.status_code == 200, set_response.text
    body = set_response.json()
    assert body["configured"] is True
    assert body["cookies_count"] == 2
    assert body["domain"] == "exemplo.dev"

    get_response = client.get(f"/ai-tools/{tool['id']}/cookies", headers=admin_headers)
    assert get_response.json()["cookies_count"] == 2

    delete_response = client.delete(f"/ai-tools/{tool['id']}/cookies", headers=admin_headers)
    assert delete_response.status_code == 204

    after_delete = client.get(f"/ai-tools/{tool['id']}/cookies", headers=admin_headers)
    assert after_delete.json()["configured"] is False


def test_cookies_reject_empty_list(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminvazio")
    tool = _create_tool(client, admin_headers, name="VazioIA")

    response = client.put(
        f"/ai-tools/{tool['id']}/cookies", json={"cookies_data": []}, headers=admin_headers
    )
    assert response.status_code == 400
