"""Cliente HTTP do Mercado Pago.

Porta as três chamadas reais que o app desktop fazia — em
`core/api/mercadopago_worker.py` (`generate_pix_payment`, `test_connection`)
e `core/widgets/settings/dialogs/payment_status_checker.py`
(`check_payment_status`, polling em thread Qt a cada 5s por até 5min) — como
funções assíncronas puras, sem `QThread`/sinais. O polling do desktop vira,
na versão web, duas coisas: o webhook real do Mercado Pago (ver
`app/api/routes/payments.py`, rota `/payments/webhook/mercadopago`) e uma
re-checagem sob demanda quando o painel consulta `GET /payments/{id}`
enquanto o pagamento ainda está pendente — ver plano de migração, seção 7.

Escopo atual, por decisão de produto: **PIX** (via este cliente) e
**cartão de crédito** (`charge_card`, tokenizado no frontend via Mercado
Pago Bricks — o backend nunca vê o número do cartão, só o token). Boleto
existiu brevemente nesta migração e foi removido antes de qualquer uso em
produção — troca por USDT (rede TRC20, self-custodial, sem passar pelo
Mercado Pago — ver `app/services/tron_client.py`).
"""
from typing import Optional

import httpx

MERCADOPAGO_API_BASE_URL = "https://api.mercadopago.com"
_REQUEST_TIMEOUT_SECONDS = 30.0


class MercadoPagoError(Exception):
    """Erro ao chamar a API do Mercado Pago — mensagem já pronta para log/UI."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _headers(access_token: str, idempotency_key: Optional[str] = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key
    return headers


def _raise_for_error(response: httpx.Response) -> None:
    if response.status_code in (200, 201):
        return
    try:
        body = response.json()
        message = body.get("message", f"Erro HTTP {response.status_code}")
        cause = body.get("cause") or []
        if cause:
            details = "; ".join(
                f"{c.get('code', '')}: {c.get('description', '')}" for c in cause
            )
            message = f"{message} — {details}"
    except Exception:
        message = f"Erro HTTP {response.status_code}: {response.text[:300]}"
    raise MercadoPagoError(message, status_code=response.status_code)


async def test_connection(access_token: str) -> bool:
    """Equivalente de MercadoPagoAPIWorker.test_connection — só confirma que
    o token é válido consultando um endpoint de leitura barato."""
    async with httpx.AsyncClient(base_url=MERCADOPAGO_API_BASE_URL, timeout=10.0) as client:
        response = await client.get("/v1/payment_methods", headers=_headers(access_token))
    return response.status_code == 200


async def create_pix_payment(
    access_token: str,
    *,
    amount: float,
    description: str,
    payer_email: str,
    external_reference: str,
    expiration_minutes: int = 30,
) -> dict:
    """Cria um pagamento PIX real. Equivalente de
    MercadoPagoAPIWorker.generate_pix_payment, sem a lógica de comissão do
    desktop (split de afiliados não foi portado — ver backend/README.md)."""
    from datetime import datetime, timedelta, timezone

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)

    payload = {
        "transaction_amount": round(float(amount), 2),
        "description": description,
        "payment_method_id": "pix",
        "payer": {"email": payer_email},
        "external_reference": external_reference,
        "date_of_expiration": expires_at.isoformat(timespec="milliseconds"),
    }

    async with httpx.AsyncClient(
        base_url=MERCADOPAGO_API_BASE_URL, timeout=_REQUEST_TIMEOUT_SECONDS
    ) as client:
        response = await client.post(
            "/v1/payments",
            headers=_headers(access_token, idempotency_key=f"pix_{external_reference}"),
            json=payload,
        )
    _raise_for_error(response)
    data = response.json()

    transaction_data = data.get("point_of_interaction", {}).get("transaction_data", {})
    qr_code = transaction_data.get("qr_code", "")
    if not qr_code:
        raise MercadoPagoError("QR Code não encontrado na resposta do Mercado Pago")

    return {
        "id": str(data.get("id")),
        "status": data.get("status", "pending"),
        "qr_code": qr_code,
        "qr_code_base64": transaction_data.get("qr_code_base64", ""),
        "date_of_expiration": data.get("date_of_expiration"),
    }


async def charge_card(
    access_token: str,
    *,
    token: str,
    amount: float,
    description: str,
    installments: int,
    payment_method_id: str,
    payer_email: str,
    payer_cpf: str,
    external_reference: str,
) -> dict:
    """Cobra um cartão já tokenizado no navegador do cliente via Mercado
    Pago Bricks (`Card Payment Brick`, `sdk.mercadopago.com/js/v2`) — o
    número do cartão nunca passa pelo nosso backend, só o `token` que o
    Brick gera (exigência de PCI compliance do próprio Mercado Pago).

    `payment_method_id` (ex.: "visa", "master") e `installments` também vêm
    prontos do Brick — ele já detecta a bandeira e mostra o seletor de
    parcelas. Diferente do PIX, a resposta aqui já vem com o status final
    (aprovado/recusado) — cartão não fica "pendente" esperando webhook do
    jeito que PIX fica.
    """
    payload = {
        "transaction_amount": round(float(amount), 2),
        "token": token,
        "description": description,
        "installments": installments,
        "payment_method_id": payment_method_id,
        "external_reference": external_reference,
        "payer": {
            "email": payer_email,
            "identification": {"type": "CPF", "number": payer_cpf},
        },
    }

    async with httpx.AsyncClient(
        base_url=MERCADOPAGO_API_BASE_URL, timeout=_REQUEST_TIMEOUT_SECONDS
    ) as client:
        response = await client.post(
            "/v1/payments",
            headers=_headers(access_token, idempotency_key=f"cartao_{external_reference}"),
            json=payload,
        )
    _raise_for_error(response)
    data = response.json()

    return {
        "id": str(data.get("id")),
        "status": data.get("status", "pending"),
        "status_detail": data.get("status_detail", ""),
        "payment_method_id": data.get("payment_method_id", payment_method_id),
        "installments": data.get("installments", installments),
    }


async def get_payment(access_token: str, payment_id: str) -> dict:
    """Consulta o status atual de um pagamento. Equivalente de
    PaymentStatusChecker.check_payment_status, chamado sob demanda (webhook
    ou polling do painel) em vez de em loop de thread."""
    async with httpx.AsyncClient(base_url=MERCADOPAGO_API_BASE_URL, timeout=10.0) as client:
        response = await client.get(f"/v1/payments/{payment_id}", headers=_headers(access_token))
    _raise_for_error(response)
    return response.json()
