"""Testes de histórico de downloads (Fase 4)."""
import hashlib

from app.crud import user as user_crud


def _phone_for(username: str) -> str:
    # Hash do username inteiro (não só um prefixo) para telefone único e
    # determinístico por teste — evita colisão de UNIQUE constraint entre
    # usernames que compartilham prefixo (ex.: "indicado2"/"indicador2").
    digest = hashlib.md5(username.encode()).hexdigest()
    digits = "".join(str(int(ch, 16) % 10) for ch in digest[:8])
    return ("119" + digits)[:11]


def _register_and_login(client, db_session, username: str) -> dict:
    db = db_session()
    try:
        ok, _ = user_crud.register_user(
            db,
            username=username,
            password="SenhaForte123",
            email=f"{username}@nuvion.dev",
            name="Usuário de Teste",
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


def test_downloads_require_auth(client):
    assert client.get("/downloads/me").status_code == 401


def test_register_and_list_download(client, db_session):
    headers = _register_and_login(client, db_session, "baixador")

    created = client.post(
        "/downloads",
        json={"file_name": "relatorio.pdf", "url": "https://exemplo.dev/relatorio.pdf"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "in_progress"

    listing = client.get("/downloads/me", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["file_name"] == "relatorio.pdf"


def test_update_download_status(client, db_session):
    headers = _register_and_login(client, db_session, "atualizador")

    created = client.post(
        "/downloads", json={"file_name": "arquivo.zip"}, headers=headers
    ).json()

    updated = client.patch(
        f"/downloads/{created['id']}", json={"status": "completed"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"
    assert updated.json()["end_time"] is not None


def test_downloads_are_scoped_per_user(client, db_session):
    headers_a = _register_and_login(client, db_session, "usuariodown1")
    headers_b = _register_and_login(client, db_session, "usuariodown2")

    client.post("/downloads", json={"file_name": "a.txt"}, headers=headers_a)

    listing_b = client.get("/downloads/me", headers=headers_b)
    assert listing_b.json() == []


def test_cannot_update_other_users_download(client, db_session):
    headers_a = _register_and_login(client, db_session, "donodown")
    headers_b = _register_and_login(client, db_session, "intrusodown")

    created = client.post("/downloads", json={"file_name": "privado.txt"}, headers=headers_a).json()

    response = client.patch(
        f"/downloads/{created['id']}", json={"status": "completed"}, headers=headers_b
    )
    assert response.status_code == 404
