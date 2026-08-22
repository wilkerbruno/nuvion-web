"""Testes de ponta a ponta do fluxo de autenticação: registro, login,
/users/me e /dashboard/me. Usa SQLite em memória via a fixture `db_session`
(conftest.py) — não precisa de um MySQL real para rodar (inclusive no CI)."""
from app.crud import user as user_crud


def _seed_referrer(db) -> str:
    ok, user_id = user_crud.register_user(
        db,
        username="fundador",
        password="SenhaForte123",
        email="fundador@nuvion.dev",
        name="Fundador",
        phone="11999990000",
        account_type="Admin",
        status="Ativo",
        bypass_referral_validation=True,
    )
    assert ok, user_id
    return db.query(user_crud.User).filter(user_crud.User.id == user_id).first().referral_code


def _referral_code(db_session) -> str:
    db = db_session()
    try:
        return _seed_referrer(db)
    finally:
        db.close()


def test_register_requires_referral_code(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "semindicacao",
            "email": "semindicacao@nuvion.dev",
            "password": "SenhaForte123",
            "name": "Sem Indicação",
            "phone": "11988887777",
            "referral_code": "",
        },
    )
    assert response.status_code in (400, 422)


def test_register_login_and_me_flow(client, db_session):
    referral_code = _referral_code(db_session)

    register_response = client.post(
        "/auth/register",
        json={
            "username": "novato",
            "email": "novato@nuvion.dev",
            "password": "SenhaForte123",
            "name": "Novato da Silva",
            "phone": "11988887777",
            "referral_code": referral_code,
        },
    )
    assert register_response.status_code == 201, register_response.text
    body = register_response.json()
    assert body["username"] == "novato"
    assert "password_hash" not in body

    login_response = client.post(
        "/auth/login", json={"username_or_email": "novato", "password": "SenhaForte123"}
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    me_response = client.get("/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "novato"

    dashboard_response = client.get("/dashboard/me", headers=headers)
    assert dashboard_response.status_code == 200
    dashboard_body = dashboard_response.json()
    assert dashboard_body["user"]["username"] == "novato"
    assert "status" in dashboard_body["payment_status"]

    refresh_response = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]


def test_login_with_wrong_password_fails(client, db_session):
    referral_code = _referral_code(db_session)
    client.post(
        "/auth/register",
        json={
            "username": "outro",
            "email": "outro@nuvion.dev",
            "password": "SenhaForte123",
            "name": "Outro Usuário",
            "phone": "11977776666",
            "referral_code": referral_code,
        },
    )

    response = client.post(
        "/auth/login", json={"username_or_email": "outro", "password": "senha-errada"}
    )
    assert response.status_code == 401


def test_me_without_token_is_unauthorized(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_profile_update(client, db_session):
    referral_code = _referral_code(db_session)
    client.post(
        "/auth/register",
        json={
            "username": "perfilteste",
            "email": "perfilteste@nuvion.dev",
            "password": "SenhaForte123",
            "name": "Perfil Teste",
            "phone": "11966665555",
            "referral_code": referral_code,
        },
    )
    login = client.post(
        "/auth/login", json={"username_or_email": "perfilteste", "password": "SenhaForte123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.patch("/users/me", json={"name": "Nome Atualizado"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Nome Atualizado"
