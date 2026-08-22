"""Testes de configuração de pagamento (admin-only) — Fase 3."""
from app.crud import user as user_crud
from app.services import mercadopago_client


def _phone_for(username: str) -> str:
    digits = "".join(str((ord(c) + i) % 10) for i, c in enumerate(username))
    return ("119" + digits + "0000000")[:11]


def _auth_headers(client, db_session, username: str, account_type: str = "Membro") -> dict:
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


def test_payment_config_requires_auth(client):
    response = client.get("/admin/payment-config")
    assert response.status_code == 401


def test_payment_config_requires_admin(client, db_session):
    headers = _auth_headers(client, db_session, "usuariocomum")
    response = client.get("/admin/payment-config", headers=headers)
    assert response.status_code == 403


def test_admin_can_read_and_update_config_with_masked_secrets(client, db_session):
    headers = _auth_headers(client, db_session, "adminpagamento", account_type="Admin")

    get_response = client.get("/admin/payment-config", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["access_token_configured"] is False

    update_response = client.put(
        "/admin/payment-config",
        json={"access_token": "APP_USR-super-secreto", "pix_key": "chave@pix.dev"},
        headers=headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()

    # O segredo nunca deve aparecer em texto puro na resposta.
    assert "APP_USR-super-secreto" not in str(body)
    assert body["access_token_configured"] is True
    assert body["pix_key"] == "chave@pix.dev"


def test_admin_can_configure_usdt_wallet_and_prices(client, db_session):
    headers = _auth_headers(client, db_session, "adminusdt", account_type="Admin")

    update_response = client.put(
        "/admin/payment-config",
        json={
            "usdt_wallet_address": "TXYZWALLETADDRESSFORTESTS000000000",
            "usdt_network": "TRC20",
            "standard_amount_usdt": "19.99",
        },
        headers=headers,
    )
    assert update_response.status_code == 200
    body = update_response.json()
    # Endereço de carteira não é segredo — volta em texto puro (diferente
    # de access_token/public_key).
    assert body["usdt_wallet_address"] == "TXYZWALLETADDRESSFORTESTS000000000"
    assert body["usdt_network"] == "TRC20"
    assert body["standard_amount_usdt"] == "19.99"


def test_admin_test_connection(client, db_session, monkeypatch):
    headers = _auth_headers(client, db_session, "adminconexao", account_type="Admin")
    client.put(
        "/admin/payment-config", json={"access_token": "TEST-TOKEN"}, headers=headers
    )

    async def fake_test_connection(access_token):
        return True

    monkeypatch.setattr(mercadopago_client, "test_connection", fake_test_connection)

    response = client.post("/admin/payment-config/test-connection", headers=headers)
    assert response.status_code == 200
    assert response.json()["ok"] is True
