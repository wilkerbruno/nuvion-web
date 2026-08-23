"""Testes do CRUD de admin do catálogo de recompensas (`/admin/rewards`,
ver app/api/routes/admin_rewards.py e app/models/reward.py)."""
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


def _admin_headers(client, db_session, username: str = "adminrecompensa") -> dict:
    return _register_and_login(client, db_session, username, account_type="Admin")


def test_admin_rewards_requires_auth(client):
    assert client.get("/admin/rewards").status_code == 401


def test_only_admin_can_list_or_create_rewards(client, db_session):
    user_headers = _register_and_login(client, db_session, "usuariocomumrw")

    forbidden_list = client.get("/admin/rewards", headers=user_headers)
    assert forbidden_list.status_code == 403

    forbidden_create = client.post(
        "/admin/rewards",
        json={"icon": "🎁", "title": "X", "description": "y", "points": 10},
        headers=user_headers,
    )
    assert forbidden_create.status_code == 403


def test_admin_lists_seeded_default_rewards(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminlistarw")

    listing = client.get("/admin/rewards", headers=admin_headers)
    assert listing.status_code == 200
    # A tabela `rewards` é semeada pelo conftest com o catálogo antigo do
    # JSON (ver reward_service.seed_default_rewards) — deve vir não-vazia
    # mesmo sem nenhuma recompensa criada neste teste.
    assert len(listing.json()) >= 1
    assert all("points" in item for item in listing.json())


def test_admin_creates_updates_and_deletes_reward(client, db_session):
    admin_headers = _admin_headers(client, db_session, "admincrudrw")

    created = client.post(
        "/admin/rewards",
        json={"icon": "🎉", "title": "Recompensa Nova", "description": "desc", "points": 150},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    reward = created.json()
    assert reward["title"] == "Recompensa Nova"
    assert reward["points"] == 150
    assert reward["available"] is True

    updated = client.patch(
        f"/admin/rewards/{reward['id']}",
        json={"points": 200, "available": False},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["points"] == 200
    assert updated.json()["available"] is False
    assert updated.json()["title"] == "Recompensa Nova"  # não mexido, permanece

    # A recompensa desativada some do catálogo público de recompensas
    # disponíveis? Não — a rota pública /rewards/catalog não filtra por
    # `available`, é o front que decide o que exibir; aqui só confirmamos
    # que o admin consegue ler o novo estado de volta.
    fetched_after_update = client.get("/admin/rewards", headers=admin_headers)
    match = next(r for r in fetched_after_update.json() if r["id"] == reward["id"])
    assert match["available"] is False

    deleted = client.delete(f"/admin/rewards/{reward['id']}", headers=admin_headers)
    assert deleted.status_code == 204

    after_delete = client.get("/admin/rewards", headers=admin_headers)
    assert all(r["id"] != reward["id"] for r in after_delete.json())


def test_update_and_delete_unknown_reward_404(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminnaoexisterw")

    update_missing = client.patch(
        "/admin/rewards/nao-existe", json={"points": 10}, headers=admin_headers
    )
    assert update_missing.status_code == 404

    delete_missing = client.delete("/admin/rewards/nao-existe", headers=admin_headers)
    assert delete_missing.status_code == 404


def test_new_reward_appears_in_public_catalog(client, db_session):
    admin_headers = _admin_headers(client, db_session, "adminpubrw")
    user_headers = _register_and_login(client, db_session, "userverecatalogo")

    created = client.post(
        "/admin/rewards",
        json={"icon": "🏆", "title": "Troféu Exclusivo", "description": "raro", "points": 500},
        headers=admin_headers,
    )
    assert created.status_code == 201

    catalog = client.get("/rewards/catalog", headers=user_headers)
    assert catalog.status_code == 200
    assert any(item["title"] == "Troféu Exclusivo" for item in catalog.json())
