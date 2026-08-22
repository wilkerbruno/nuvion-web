"""Testes de notificações (Fase 4)."""
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


def test_notifications_require_auth(client):
    assert client.get("/notifications/me").status_code == 401


def test_empty_notifications_and_unread_count(client, db_session):
    headers = _register_and_login(client, db_session, "semnotif")

    listing = client.get("/notifications/me", headers=headers)
    assert listing.status_code == 200
    assert listing.json() == []

    unread = client.get("/notifications/me/unread-count", headers=headers)
    assert unread.json()["unread_count"] == 0


def test_only_admin_can_broadcast(client, db_session):
    user_headers = _register_and_login(client, db_session, "usuarionormal")
    response = client.post(
        "/admin/notifications/broadcast",
        json={"title": "Aviso", "message": "Manutenção programada"},
        headers=user_headers,
    )
    assert response.status_code == 403


def test_broadcast_reaches_all_users_and_can_be_read(client, db_session):
    admin_headers = _register_and_login(client, db_session, "adminnotif", account_type="Admin")
    user_headers = _register_and_login(client, db_session, "recebedor")

    broadcast = client.post(
        "/admin/notifications/broadcast",
        json={"title": "Manutenção", "message": "Sistema fora do ar às 22h", "priority": "importante"},
        headers=admin_headers,
    )
    assert broadcast.status_code == 201, broadcast.text
    notification_id = broadcast.json()["id"]

    unread = client.get("/notifications/me/unread-count", headers=user_headers)
    assert unread.json()["unread_count"] == 1

    listing = client.get("/notifications/me", headers=user_headers)
    assert len(listing.json()) == 1
    assert listing.json()[0]["is_read"] is False

    read = client.post(f"/notifications/{notification_id}/read", headers=user_headers)
    assert read.status_code == 200
    assert read.json()["is_read"] is True

    unread_after = client.get("/notifications/me/unread-count", headers=user_headers)
    assert unread_after.json()["unread_count"] == 0


def test_mark_all_as_read(client, db_session):
    admin_headers = _register_and_login(client, db_session, "adminlote", account_type="Admin")
    user_headers = _register_and_login(client, db_session, "leitor")

    for i in range(3):
        client.post(
            "/admin/notifications/broadcast",
            json={"title": f"Aviso {i}", "message": "..."},
            headers=admin_headers,
        )

    read_all = client.post("/notifications/me/read-all", headers=user_headers)
    assert read_all.status_code == 200
    assert read_all.json()["marked_count"] == 3

    unread = client.get("/notifications/me/unread-count", headers=user_headers)
    assert unread.json()["unread_count"] == 0


def test_only_owner_can_delete_personal_notification(client, db_session):
    admin_headers = _register_and_login(client, db_session, "adminstats", account_type="Admin")
    other_headers = _register_and_login(client, db_session, "intruso2")

    broadcast = client.post(
        "/admin/notifications/broadcast",
        json={"title": "Global", "message": "..."},
        headers=admin_headers,
    )
    notification_id = broadcast.json()["id"]

    # Usuário comum não pode apagar notificação global.
    forbidden = client.delete(f"/notifications/{notification_id}", headers=other_headers)
    assert forbidden.status_code == 403

    # Admin pode.
    allowed = client.delete(f"/notifications/{notification_id}", headers=admin_headers)
    assert allowed.status_code == 204


def test_admin_stats_and_expired_cleanup(client, db_session):
    admin_headers = _register_and_login(client, db_session, "adminstats2", account_type="Admin")

    client.post(
        "/admin/notifications/broadcast",
        json={"title": "Com stats", "message": "..."},
        headers=admin_headers,
    )

    stats = client.get("/admin/notifications/stats", headers=admin_headers)
    assert stats.status_code == 200
    assert len(stats.json()) == 1
    assert stats.json()[0]["total_users"] >= 1

    expired = client.delete("/admin/notifications/expired", headers=admin_headers)
    assert expired.status_code == 200
    assert expired.json()["deleted_count"] == 0
