"""Testes de pagamentos: checkout PIX/cartão/USDT, status, webhook.

As chamadas reais ao Mercado Pago (app/services/mercadopago_client.py) e ao
TronGrid (app/services/tron_client.py) são substituídas por fakes via
monkeypatch — os testes não fazem nenhuma requisição de rede, só validam a
lógica de negócio (criação de Payment, idempotência, renovação de
assinatura do usuário). Boleto foi removido do produto antes de qualquer
uso em produção — não sobrou teste dele aqui de propósito."""
import hashlib
import hmac

from app.core.config import settings
from app.crud import payment_config as payment_config_crud
from app.crud import user as user_crud
from app.services import mercadopago_client, tron_client


def _phone_for(username: str) -> str:
    digits = "".join(str((ord(c) + i) % 10) for i, c in enumerate(username))
    return ("119" + digits + "0000000")[:11]


def _auth_headers(client, db_session, username: str = "pagadorteste", **user_kwargs) -> dict:
    db = db_session()
    try:
        ok, _ = user_crud.register_user(
            db,
            username=username,
            password="SenhaForte123",
            email=f"{username}@nuvion.dev",
            name="Pagador de Teste",
            phone=_phone_for(username),
            account_type=user_kwargs.pop("account_type", "Membro"),
            status=user_kwargs.pop("status", "Ativo"),
            bypass_referral_validation=True,
            **user_kwargs,
        )
        assert ok
    finally:
        db.close()

    login = client.post(
        "/auth/login", json={"username_or_email": username, "password": "SenhaForte123"}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _configure_mercadopago(
    db_session, access_token: str = "TEST-ACCESS-TOKEN", public_key: str = "TEST-PUBLIC-KEY"
):
    db = db_session()
    try:
        payment_config_crud.create_or_update(
            db,
            payment_config_crud.DEFAULT_CONFIG_KEY,
            {
                "access_token": access_token,
                "public_key": public_key,
                "is_active": True,
                "standard_amount": "97.00",
            },
        )
    finally:
        db.close()


def _configure_usdt(
    db_session,
    wallet_address: str = "TXYZWALLETADDRESSFORTESTS000000000",
    standard_amount_usdt: str = "19.99",
):
    db = db_session()
    try:
        payment_config_crud.create_or_update(
            db,
            payment_config_crud.DEFAULT_CONFIG_KEY,
            {
                "usdt_wallet_address": wallet_address,
                "usdt_network": "TRC20",
                "standard_amount_usdt": standard_amount_usdt,
                "is_active": True,
            },
        )
    finally:
        db.close()


async def _fake_create_pix_payment(access_token, **kwargs):
    return {
        "id": "mp-pix-123",
        "status": "pending",
        "qr_code": "00020101...copia-e-cola",
        "qr_code_base64": "data:image/png;base64,AAAA",
        "date_of_expiration": "2026-08-22T12:00:00.000Z",
    }


async def _fake_charge_card_approved(access_token, **kwargs):
    return {
        "id": "mp-card-789",
        "status": "approved",
        "status_detail": "accredited",
        "payment_method_id": kwargs.get("payment_method_id", "visa"),
        "installments": kwargs.get("installments", 1),
    }


async def _fake_charge_card_rejected(access_token, **kwargs):
    return {
        "id": "mp-card-000",
        "status": "rejected",
        "status_detail": "cc_rejected_insufficient_amount",
        "payment_method_id": kwargs.get("payment_method_id", "visa"),
        "installments": kwargs.get("installments", 1),
    }


def test_prices_requires_auth(client):
    response = client.get("/payments/prices")
    assert response.status_code == 401


def test_prices_returns_configured_brl_and_usdt_amounts(client, db_session):
    _configure_mercadopago(db_session)
    _configure_usdt(db_session)
    headers = _auth_headers(client, db_session, "precosuser")

    response = client.get("/payments/prices", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["brl"]["Standard"] == 97.00
    assert "Premium" in body["brl"] and "VIP" in body["brl"]
    assert body["usdt"]["Standard"] == 19.99
    # Premium/VIP não têm preço em USDT configurado no fixture -> None
    assert body["usdt"]["Premium"] is None


def test_checkout_requires_auth(client):
    response = client.post("/payments/checkout", json={"method": "pix"})
    assert response.status_code == 401


def test_checkout_without_config_returns_503(client, db_session):
    headers = _auth_headers(client, db_session)
    response = client.post("/payments/checkout", json={"method": "pix"}, headers=headers)
    assert response.status_code == 503


def test_checkout_pix_success(client, db_session, monkeypatch):
    monkeypatch.setattr(mercadopago_client, "create_pix_payment", _fake_create_pix_payment)
    _configure_mercadopago(db_session)
    headers = _auth_headers(client, db_session, "pixuser")

    response = client.post("/payments/checkout", json={"method": "pix"}, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["payment_method"] == "pix"
    assert body["status"] == "Pendente"
    assert body["transaction_id"] == "mp-pix-123"
    assert body["payment_details"]["qr_code"] == "00020101...copia-e-cola"
    assert body["amount"] == 97.00


def test_checkout_cartao_requires_cpf_and_token(client, db_session, monkeypatch):
    monkeypatch.setattr(mercadopago_client, "charge_card", _fake_charge_card_approved)
    _configure_mercadopago(db_session)
    headers = _auth_headers(client, db_session, "cartaosemtoken")

    response = client.post("/payments/checkout", json={"method": "cartao"}, headers=headers)
    assert response.status_code == 422


def test_checkout_cartao_approved(client, db_session, monkeypatch):
    monkeypatch.setattr(mercadopago_client, "charge_card", _fake_charge_card_approved)
    _configure_mercadopago(db_session)
    headers = _auth_headers(client, db_session, "cartaouser")

    response = client.post(
        "/payments/checkout",
        json={
            "method": "cartao",
            "cpf": "12345678909",
            "card_token": "fake-brick-token",
            "card_payment_method_id": "visa",
            "installments": 3,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["payment_method"] == "cartao"
    assert body["transaction_id"] == "mp-card-789"
    # Diferente do PIX, cartão resolve na hora — já vem "Confirmado".
    assert body["status"] == "Confirmado"
    assert body["payment_date"] is not None


def test_checkout_cartao_rejected_stays_pending_then_cancelado(client, db_session, monkeypatch):
    monkeypatch.setattr(mercadopago_client, "charge_card", _fake_charge_card_rejected)
    _configure_mercadopago(db_session)
    headers = _auth_headers(client, db_session, "cartaorecusado")

    response = client.post(
        "/payments/checkout",
        json={
            "method": "cartao",
            "cpf": "12345678909",
            "card_token": "fake-brick-token",
            "card_payment_method_id": "visa",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "Cancelado"
    assert body["payment_details"]["status_detail"] == "cc_rejected_insufficient_amount"


def test_checkout_usdt_without_config_returns_503(client, db_session):
    headers = _auth_headers(client, db_session, "usdtsemconfig")
    response = client.post("/payments/checkout", json={"method": "usdt"}, headers=headers)
    assert response.status_code == 503


def test_checkout_usdt_success(client, db_session):
    _configure_usdt(db_session)
    headers = _auth_headers(client, db_session, "usdtuser")

    response = client.post("/payments/checkout", json={"method": "usdt"}, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["payment_method"] == "usdt"
    assert body["status"] == "Pendente"
    assert body["amount"] == 19.99
    assert body["crypto_amount"] == 19.99
    assert body["payment_details"]["wallet_address"] == "TXYZWALLETADDRESSFORTESTS000000000"
    assert body["payment_details"]["network"] == "TRC20"
    assert body["payment_details"]["usdt_amount"] == "19.990000"


def test_checkout_usdt_generates_unique_amount_per_pending_payment(client, db_session):
    _configure_usdt(db_session)
    headers_a = _auth_headers(client, db_session, "usdtdupa")
    headers_b = _auth_headers(client, db_session, "usdtdupb")

    payment_a = client.post("/payments/checkout", json={"method": "usdt"}, headers=headers_a).json()
    payment_b = client.post("/payments/checkout", json={"method": "usdt"}, headers=headers_b).json()

    assert payment_a["crypto_amount"] != payment_b["crypto_amount"]
    # O segundo pedido pendente recebe o próximo micro-incremento (0.000001).
    assert round(payment_b["crypto_amount"] - payment_a["crypto_amount"], 6) == 0.000001


def test_get_payment_status_usdt_confirms_when_transfer_found(client, db_session, monkeypatch):
    _configure_usdt(db_session)
    headers = _auth_headers(client, db_session, "usdtconfirma")

    checkout = client.post("/payments/checkout", json={"method": "usdt"}, headers=headers)
    payment_id = checkout.json()["id"]
    expected_amount = checkout.json()["crypto_amount"]

    async def fake_find_transfer(wallet_address, expected_amount_usdt, since_unix_ms, api_key=""):
        assert wallet_address == "TXYZWALLETADDRESSFORTESTS000000000"
        assert abs(expected_amount_usdt - expected_amount) < 1e-9
        return {"transaction_id": "tron-tx-abc123"}

    monkeypatch.setattr(tron_client, "find_incoming_usdt_transfer", fake_find_transfer)

    status_response = client.get(f"/payments/{payment_id}", headers=headers)
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "Confirmado"
    assert body["transaction_id"] == "tron-tx-abc123"


def test_get_payment_status_usdt_stays_pending_when_no_transfer_found(
    client, db_session, monkeypatch
):
    _configure_usdt(db_session)
    headers = _auth_headers(client, db_session, "usdtaguardando")

    checkout = client.post("/payments/checkout", json={"method": "usdt"}, headers=headers)
    payment_id = checkout.json()["id"]

    async def fake_find_transfer(wallet_address, expected_amount_usdt, since_unix_ms, api_key=""):
        return None

    monkeypatch.setattr(tron_client, "find_incoming_usdt_transfer", fake_find_transfer)

    status_response = client.get(f"/payments/{payment_id}", headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "Pendente"


def test_mercadopago_public_key_requires_config(client, db_session):
    headers = _auth_headers(client, db_session, "semchavepublica")
    response = client.get("/payments/mercadopago-public-key", headers=headers)
    assert response.status_code == 503


def test_mercadopago_public_key_returns_value(client, db_session):
    _configure_mercadopago(db_session, public_key="APP-USR-public-key-123")
    headers = _auth_headers(client, db_session, "comchavepublica")

    response = client.get("/payments/mercadopago-public-key", headers=headers)
    assert response.status_code == 200
    assert response.json()["public_key"] == "APP-USR-public-key-123"


def test_list_my_payments_scoped_per_user(client, db_session, monkeypatch):
    monkeypatch.setattr(mercadopago_client, "create_pix_payment", _fake_create_pix_payment)
    _configure_mercadopago(db_session)
    headers_a = _auth_headers(client, db_session, "pagadora")
    headers_b = _auth_headers(client, db_session, "pagadorb")

    client.post("/payments/checkout", json={"method": "pix"}, headers=headers_a)

    listing_a = client.get("/payments/me", headers=headers_a)
    listing_b = client.get("/payments/me", headers=headers_b)
    assert len(listing_a.json()) == 1
    assert listing_b.json() == []


def test_get_payment_status_confirms_and_renews_subscription(client, db_session, monkeypatch):
    monkeypatch.setattr(mercadopago_client, "create_pix_payment", _fake_create_pix_payment)
    _configure_mercadopago(db_session)
    headers = _auth_headers(client, db_session, "renovaruser")

    checkout = client.post("/payments/checkout", json={"method": "pix"}, headers=headers)
    payment_id = checkout.json()["id"]

    async def fake_get_payment(access_token, payment_id_arg):
        return {"id": "mp-pix-123", "status": "approved", "transaction_amount": 97.00}

    monkeypatch.setattr(mercadopago_client, "get_payment", fake_get_payment)

    status_response = client.get(f"/payments/{payment_id}", headers=headers)
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "Confirmado"
    assert body["payment_date"] is not None

    dashboard = client.get("/dashboard/me", headers=headers)
    dashboard_body = dashboard.json()
    assert dashboard_body["user"]["status"] == "Ativo"
    assert dashboard_body["user"]["category"] == "Standard"
    assert dashboard_body["user"]["payment_due_date"] is not None


def test_get_payment_not_owned_returns_404(client, db_session, monkeypatch):
    monkeypatch.setattr(mercadopago_client, "create_pix_payment", _fake_create_pix_payment)
    _configure_mercadopago(db_session)
    headers_a = _auth_headers(client, db_session, "dono")
    headers_b = _auth_headers(client, db_session, "intruso")

    checkout = client.post("/payments/checkout", json={"method": "pix"}, headers=headers_a)
    payment_id = checkout.json()["id"]

    response = client.get(f"/payments/{payment_id}", headers=headers_b)
    assert response.status_code == 404


def test_webhook_confirms_payment_and_is_idempotent(client, db_session, monkeypatch):
    monkeypatch.setattr(mercadopago_client, "create_pix_payment", _fake_create_pix_payment)
    _configure_mercadopago(db_session)
    headers = _auth_headers(client, db_session, "webhookuser")

    checkout = client.post("/payments/checkout", json={"method": "pix"}, headers=headers)
    assert checkout.status_code == 201

    async def fake_get_payment(access_token, payment_id_arg):
        return {"id": "mp-pix-123", "status": "approved", "transaction_amount": 97.00}

    monkeypatch.setattr(mercadopago_client, "get_payment", fake_get_payment)

    webhook_response = client.post(
        "/payments/webhook/mercadopago?type=payment&data.id=mp-pix-123",
        json={"type": "payment", "data": {"id": "mp-pix-123"}},
    )
    assert webhook_response.status_code == 200

    my_payments = client.get("/payments/me", headers=headers).json()
    assert my_payments[0]["status"] == "Confirmado"
    due_date_after_first_webhook = my_payments[0]["due_date"]

    # Reenvio do mesmo webhook (comportamento real do Mercado Pago) não pode
    # renovar a assinatura de novo.
    webhook_response_2 = client.post(
        "/payments/webhook/mercadopago?type=payment&data.id=mp-pix-123",
        json={"type": "payment", "data": {"id": "mp-pix-123"}},
    )
    assert webhook_response_2.status_code == 200

    my_payments_after = client.get("/payments/me", headers=headers).json()
    assert my_payments_after[0]["due_date"] == due_date_after_first_webhook


def test_webhook_unknown_payment_returns_200(client, db_session):
    response = client.post(
        "/payments/webhook/mercadopago?type=payment&data.id=nao-existe",
        json={"type": "payment", "data": {"id": "nao-existe"}},
    )
    assert response.status_code == 200


def test_webhook_signature_verification(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "MERCADOPAGO_WEBHOOK_SECRET", "meu-segredo-de-teste")

    wrong_signature_response = client.post(
        "/payments/webhook/mercadopago?type=payment&data.id=123",
        json={"type": "payment", "data": {"id": "123"}},
        headers={"x-signature": "ts=1,v1=assinatura-errada", "x-request-id": "req-1"},
    )
    assert wrong_signature_response.status_code == 401

    ts = "1700000000"
    request_id = "req-1"
    manifest = f"id:123;request-id:{request_id};ts:{ts};"
    valid_hash = hmac.new(
        "meu-segredo-de-teste".encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()

    valid_response = client.post(
        "/payments/webhook/mercadopago?type=payment&data.id=123",
        json={"type": "payment", "data": {"id": "123"}},
        headers={"x-signature": f"ts={ts},v1={valid_hash}", "x-request-id": request_id},
    )
    # Assinatura válida, mas nenhum Payment local com transaction_id=123 —
    # ainda assim deve responder 200 (webhook nunca falha por isso).
    assert valid_response.status_code == 200
