"""Testes de diamantes/recompensas (Fase 4)."""
import hashlib

from app.crud import user as user_crud


def _phone_for(username: str) -> str:
    # Hash do username inteiro (não só um prefixo) para telefone único e
    # determinístico por teste — evita colisão de UNIQUE constraint entre
    # usernames que compartilham prefixo (ex.: "indicado2"/"indicador2").
    digest = hashlib.md5(username.encode()).hexdigest()
    digits = "".join(str(int(ch, 16) % 10) for ch in digest[:8])
    return ("119" + digits)[:11]


def _register(db_session, username: str, **kwargs) -> str:
    db = db_session()
    try:
        ok, result = user_crud.register_user(
            db,
            username=username,
            password="SenhaForte123",
            email=f"{username}@nuvion.dev",
            name="Usuário de Teste",
            phone=_phone_for(username),
            account_type=kwargs.pop("account_type", "Membro"),
            status=kwargs.pop("status", "Ativo"),
            **kwargs,
        )
        assert ok, result
        return result
    finally:
        db.close()


def _login(client, username: str) -> dict:
    login = client.post(
        "/auth/login", json={"username_or_email": username, "password": "SenhaForte123"}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_rewards_require_auth(client):
    assert client.get("/rewards/me").status_code == 401
    assert client.get("/rewards/catalog").status_code == 401


def test_new_user_starts_with_zero_diamonds(client, db_session):
    _register(db_session, "semdiamante", bypass_referral_validation=True)
    headers = _login(client, "semdiamante")

    response = client.get("/rewards/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["diamonds"] == 0
    assert body["transactions"] == []
    assert body["claimed_rewards"] == []
    assert "referral_code" in body


def test_referral_grants_diamonds_to_both_sides(client, db_session):
    referrer_id = _register(db_session, "indicador1", bypass_referral_validation=True)

    db = db_session()
    try:
        referrer = user_crud.get_by_id(db, referrer_id)
        referral_code = referrer.referral_code
    finally:
        db.close()

    _register(db_session, "indicado1", referral_code=referral_code)

    referrer_headers = _login(client, "indicador1")
    novo_headers = _login(client, "indicado1")

    referrer_balance = client.get("/rewards/me", headers=referrer_headers).json()
    novo_balance = client.get("/rewards/me", headers=novo_headers).json()

    assert referrer_balance["diamonds"] == 50
    assert referrer_balance["transactions"][0]["type"] == "referral_bonus"
    assert novo_balance["diamonds"] == 20
    assert novo_balance["transactions"][0]["type"] == "signup_bonus"


def test_catalog_lists_static_rewards(client, db_session):
    _register(db_session, "catalogouser", bypass_referral_validation=True)
    headers = _login(client, "catalogouser")

    response = client.get("/rewards/catalog", headers=headers)
    assert response.status_code == 200
    catalog = response.json()
    assert len(catalog) >= 1
    assert all("points" in item for item in catalog)
    assert all(item["already_claimed"] is False for item in catalog)


def test_claim_reward_deducts_diamonds(client, db_session):
    from app.services import reward_service

    user_id = _register(db_session, "resgatador", bypass_referral_validation=True)

    # Credita diamantes suficientes diretamente (não depende do valor do
    # bônus de indicação bater com o preço de nenhuma recompensa do catálogo).
    db = db_session()
    try:
        user = user_crud.get_by_id(db, user_id)
        reward_service.add_diamonds(db, user, 1000, "test_setup", "saldo de teste")
    finally:
        db.close()

    headers = _login(client, "resgatador")

    catalog = client.get("/rewards/catalog", headers=headers).json()
    cheapest = min(catalog, key=lambda r: r["points"])

    claim = client.post(f"/rewards/claim/{cheapest['id']}", headers=headers)
    assert claim.status_code == 200, claim.text
    assert claim.json()["success"] is True
    assert claim.json()["diamonds"] == 1000 - cheapest["points"]

    balance = client.get("/rewards/me", headers=headers).json()
    assert cheapest["id"] in balance["claimed_rewards"]

    # Resgatar de novo deve falhar
    second_claim = client.post(f"/rewards/claim/{cheapest['id']}", headers=headers)
    assert second_claim.status_code == 400


def test_claim_reward_insufficient_balance(client, db_session):
    _register(db_session, "pobrezinho", bypass_referral_validation=True)
    headers = _login(client, "pobrezinho")

    catalog = client.get("/rewards/catalog", headers=headers).json()
    expensive = max(catalog, key=lambda r: r["points"])

    response = client.post(f"/rewards/claim/{expensive['id']}", headers=headers)
    assert response.status_code == 400


def test_claim_unknown_reward_404_equivalent(client, db_session):
    _register(db_session, "curioso", bypass_referral_validation=True)
    headers = _login(client, "curioso")

    response = client.post("/rewards/claim/nao-existe", headers=headers)
    assert response.status_code == 400
