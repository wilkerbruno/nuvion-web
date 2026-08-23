"""Testes de `/tool-bookmarks` (Fase 5) — favoritos de página por
ferramenta, salvos pela extensão. Sempre escopados ao próprio usuário."""
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


def _admin_headers(client, db_session, username: str = "adminbookmark") -> dict:
    return _register_and_login(client, db_session, username, account_type="Admin")


def _create_tool(client, admin_headers, name: str = "Ferramenta Bookmark") -> dict:
    response = client.post(
        "/ai-tools",
        json={"name": name, "url": "https://ferramenta.example.com/app"},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_bookmarks_require_auth(client):
    assert client.get("/tool-bookmarks").status_code == 401
    assert client.post("/tool-bookmarks", json={"ai_tool_id": "x", "url": "https://x.com"}).status_code == 401


def test_create_list_and_delete_bookmark(client, db_session):
    admin_headers = _admin_headers(client, db_session)
    tool = _create_tool(client, admin_headers)
    user_headers = _register_and_login(client, db_session, "userbookmark1")

    created = client.post(
        "/tool-bookmarks",
        json={
            "ai_tool_id": tool["id"],
            "url": "https://ferramenta.example.com/app/conversa/42",
            "title": "Conversa importante",
        },
        headers=user_headers,
    )
    assert created.status_code == 201, created.text
    bookmark = created.json()
    assert bookmark["ai_tool_id"] == tool["id"]
    assert bookmark["title"] == "Conversa importante"

    listing = client.get("/tool-bookmarks", headers=user_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["id"] == bookmark["id"]

    filtered = client.get(f"/tool-bookmarks?ai_tool_id={tool['id']}", headers=user_headers)
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1

    delete_response = client.delete(f"/tool-bookmarks/{bookmark['id']}", headers=user_headers)
    assert delete_response.status_code == 204

    listing_after = client.get("/tool-bookmarks", headers=user_headers)
    assert listing_after.json() == []


def test_create_bookmark_404_for_unknown_tool(client, db_session):
    user_headers = _register_and_login(client, db_session, "userbookmark404")
    response = client.post(
        "/tool-bookmarks",
        json={"ai_tool_id": "nao-existe", "url": "https://x.com"},
        headers=user_headers,
    )
    assert response.status_code == 404


def test_bookmarks_are_isolated_per_user(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminbookmark2")
    tool = _create_tool(client, admin_headers, name="Ferramenta Isolamento")

    user_a = _register_and_login(client, db_session, "userbookmarka")
    user_b = _register_and_login(client, db_session, "userbookmarkb")

    created = client.post(
        "/tool-bookmarks",
        json={"ai_tool_id": tool["id"], "url": "https://ferramenta.example.com/a"},
        headers=user_a,
    )
    assert created.status_code == 201
    bookmark_id = created.json()["id"]

    # usuário B não vê o favorito do usuário A
    listing_b = client.get("/tool-bookmarks", headers=user_b)
    assert listing_b.json() == []

    # nem consegue apagar o favorito do usuário A
    delete_response = client.delete(f"/tool-bookmarks/{bookmark_id}", headers=user_b)
    assert delete_response.status_code == 404

    # mas o usuário A continua vendo o próprio favorito normalmente
    listing_a = client.get("/tool-bookmarks", headers=user_a)
    assert len(listing_a.json()) == 1
