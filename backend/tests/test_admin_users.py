"""Testes da gestão de usuários por admin (`/admin/users`) — definir plano
(categoria) e bloquear/desbloquear via `status` (ver
app/api/routes/admin_users.py)."""
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


def _admin_headers(client, db_session, username: str = "adminusuarios") -> dict:
    return _register_and_login(client, db_session, username, account_type="Admin")


def test_admin_users_requires_auth(client):
    assert client.get("/admin/users").status_code == 401


def test_only_admin_can_list_or_update_users(client, db_session):
    user_headers = _register_and_login(client, db_session, "usuariocomumadm")

    assert client.get("/admin/users", headers=user_headers).status_code == 403
    assert (
        client.patch(
            "/admin/users/qualquer-id", json={"category": "VIP"}, headers=user_headers
        ).status_code
        == 403
    )


def test_admin_lists_and_searches_users(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminlistausers")
    _register_and_login(client, db_session, "buscavelusuario")

    listing = client.get("/admin/users", headers=admin_headers)
    assert listing.status_code == 200
    assert any(u["username"] == "buscavelusuario" for u in listing.json())

    search = client.get("/admin/users?search=buscavel", headers=admin_headers)
    assert search.status_code == 200
    assert all("buscavel" in u["username"] for u in search.json())


def test_admin_changes_user_plan(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminplano")
    _register_and_login(client, db_session, "usuarioplano")

    db = db_session()
    try:
        target = user_crud.get_by_username(db, "usuarioplano")
        target_id = target.id
        assert target.category == "Standard"
    finally:
        db.close()

    updated = client.patch(
        f"/admin/users/{target_id}", json={"category": "VIP"}, headers=admin_headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["category"] == "VIP"

    fetched = client.get(f"/admin/users/{target_id}", headers=admin_headers)
    assert fetched.json()["category"] == "VIP"


def test_admin_blocks_and_unblocks_user(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminbloqueia")
    user_headers = _register_and_login(client, db_session, "usuariobloqueavel")

    db = db_session()
    try:
        target = user_crud.get_by_username(db, "usuariobloqueavel")
        target_id = target.id
    finally:
        db.close()

    blocked = client.patch(
        f"/admin/users/{target_id}", json={"status": "Bloqueado"}, headers=admin_headers
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["status"] == "Bloqueado"

    # Usuário bloqueado não consegue mais logar
    relogin = client.post(
        "/auth/login",
        json={"username_or_email": "usuariobloqueavel", "password": "SenhaForte123"},
    )
    assert relogin.status_code in (400, 401, 403)

    # E a sessão já ativa perde acesso a rotas autenticadas
    still_authed = client.get("/auth/me", headers=user_headers)
    assert still_authed.status_code == 403

    unblocked = client.patch(
        f"/admin/users/{target_id}", json={"status": "Ativo"}, headers=admin_headers
    )
    assert unblocked.status_code == 200
    assert unblocked.json()["status"] == "Ativo"

    relogin_after = client.post(
        "/auth/login",
        json={"username_or_email": "usuariobloqueavel", "password": "SenhaForte123"},
    )
    assert relogin_after.status_code == 200


def test_admin_cannot_block_own_account(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminautobloqueio")

    db = db_session()
    try:
        admin_user = user_crud.get_by_username(db, "adminautobloqueio")
        admin_id = admin_user.id
    finally:
        db.close()

    response = client.patch(
        f"/admin/users/{admin_id}", json={"status": "Bloqueado"}, headers=admin_headers
    )
    assert response.status_code == 400


def test_update_unknown_user_404(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminnaoexisteuser")

    response = client.patch(
        "/admin/users/nao-existe", json={"category": "VIP"}, headers=admin_headers
    )
    assert response.status_code == 404


def test_invalid_category_rejected(client, db_session):
    admin_headers = _admin_headers(client, db_session, "admincategoriainvalida")
    _register_and_login(client, db_session, "usuariocategoriainvalida")

    db = db_session()
    try:
        target = user_crud.get_by_username(db, "usuariocategoriainvalida")
        target_id = target.id
    finally:
        db.close()

    response = client.patch(
        f"/admin/users/{target_id}", json={"category": "Diamante"}, headers=admin_headers
    )
    assert response.status_code == 422
