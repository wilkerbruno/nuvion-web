"""Rotas de pagamento — checkout PIX/cartão/USDT, histórico, status e o
webhook real do Mercado Pago.

Mudança estrutural em relação ao desktop (plano de migração, seção 7): lá,
uma `QThread` (`PaymentStatusChecker`) ficava consultando
`GET /v1/payments/{id}` a cada 5 segundos por até 5 minutos até o pagamento
mudar de status. Aqui isso vira coisas mais baratas: o webhook real do
Mercado Pago (`/payments/webhook/mercadopago`, chamado pelo próprio MP
assim que o status muda, só vale para PIX/cartão) e uma re-checagem sob
demanda em `GET /payments/{id}` — o painel pode chamar essa rota em
intervalo curto enquanto mostra o QR Code/tela de cartão/carteira USDT, sem
manter nenhuma thread viva no back-end. Pra USDT não existe webhook (não há
provedor terceiro) — `GET /payments/{id}` é a ÚNICA forma de detectar que
um pagamento em USDT chegou, consultando o TronGrid sob demanda (ver
`app/services/tron_client.py` e docs/PAGAMENTOS_CRIPTO.md).
"""
import hashlib
import hmac
import json
import uuid
from datetime import timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.logging import LOGGER
from app.crud import payment as payment_crud
from app.crud import payment_config as payment_config_crud
from app.db.session import get_db
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import CheckoutRequest, MercadoPagoPublicKey, PaymentPublic
from app.services import mercadopago_client, tron_client
from app.services.mercadopago_client import MercadoPagoError

router = APIRouter(prefix="/payments", tags=["payments"])

# Mapa de status do Mercado Pago -> status do nosso modelo Payment.
_MP_STATUS_MAP = {
    "approved": "Confirmado",
    "accredited": "Confirmado",
    "pending": "Pendente",
    "in_process": "Pendente",
    "rejected": "Cancelado",
    "cancelled": "Cancelado",
    "refunded": "Cancelado",
    "charged_back": "Cancelado",
}


def _get_active_access_token(db: Session) -> str:
    config = payment_config_crud.get_active_config(db) or payment_config_crud.get_by_key(db)
    token = (config.access_token if config else "") or settings.MERCADOPAGO_ACCESS_TOKEN
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pagamentos não configurados no momento — contate o suporte",
        )
    return token


@router.get("/prices")
def get_prices(
    _current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict:
    """Valores por categoria em BRL e USDT — não é segredo (o admin define
    via /admin/payment-config), só fica atrás de auth por não fazer sentido
    expor sem contexto de conta. `usdt` vem `null` pra uma categoria que o
    admin ainda não configurou preço em USDT — nesse caso o checkout em
    USDT não fica disponível pra ela (ver POST /payments/checkout)."""
    categories = ("Standard", "Premium", "VIP")
    return {
        "brl": {c: payment_config_crud.get_amount_by_category(db, c) for c in categories},
        "usdt": {c: payment_config_crud.get_usdt_amount_by_category(db, c) for c in categories},
    }


@router.get("/mercadopago-public-key", response_model=MercadoPagoPublicKey)
def get_mercadopago_public_key(
    _current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """A `public_key` do Mercado Pago é, por natureza, feita pra ser
    exposta no navegador — é o que o Card Payment Brick usa pra tokenizar o
    cartão no cliente (diferente do `access_token`, que é secreto e nunca
    sai do backend). Ver `PaymentConfigPublic` em app/schemas/payment_config.py
    pra comparação."""
    config = payment_config_crud.get_active_config(db) or payment_config_crud.get_by_key(db)
    public_key = (config.public_key if config else "") or ""
    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pagamento por cartão não configurado no momento — contate o suporte",
        )
    return MercadoPagoPublicKey(public_key=public_key)


@router.get("/me", response_model=List[PaymentPublic])
def list_my_payments(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return payment_crud.get_user_payments(db, current_user.id)


@router.post("/checkout", response_model=PaymentPublic, status_code=status.HTTP_201_CREATED)
async def checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    category = payload.category or current_user.category

    if payload.method == "usdt":
        return await _checkout_usdt(db, current_user, category)

    amount = payment_config_crud.get_amount_by_category(db, category)
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Categoria {category} não tem cobrança configurada",
        )

    access_token = _get_active_access_token(db)
    external_reference = f"{payload.method}_{uuid.uuid4()}"
    description = f"Assinatura Nuvion — {category}"

    payment = payment_crud.create_payment(
        db,
        user_id=current_user.id,
        amount=amount,
        payment_method=payload.method,
        description=category,
    )

    try:
        if payload.method == "pix":
            result = await mercadopago_client.create_pix_payment(
                access_token,
                amount=amount,
                description=description,
                payer_email=current_user.email,
                external_reference=external_reference,
            )
        else:  # "cartao"
            cpf = (payload.cpf or current_user.cpf or "").strip()
            if not cpf or not payload.card_token or not payload.card_payment_method_id:
                payment_crud.mark_failed(db, payment)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Pagamento por cartão exige CPF e o token gerado pelo formulário de cartão",
                )
            result = await mercadopago_client.charge_card(
                access_token,
                token=payload.card_token,
                amount=amount,
                description=description,
                installments=payload.installments or 1,
                payment_method_id=payload.card_payment_method_id,
                payer_email=current_user.email,
                payer_cpf=cpf,
                external_reference=external_reference,
            )
    except MercadoPagoError as err:
        payment_crud.mark_failed(db, payment)
        LOGGER.error(f"Falha ao gerar {payload.method} para {current_user.username}: {err}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err)) from err

    payment.transaction_id = result["id"]
    payment.payment_details = result
    db.commit()
    db.refresh(payment)

    if payload.method == "cartao":
        # Cartão resolve na hora (aprovado/recusado) — diferente do PIX, não
        # fica esperando webhook nem checagem posterior pra dar o primeiro
        # status. Reaproveita o mesmo mapeamento de status usado pelo
        # webhook/recheck, então o comportamento fica consistente.
        payment = _apply_mp_status(db, payment, result)

    return payment


async def _checkout_usdt(db: Session, current_user: User, category: str) -> Payment:
    wallet = payment_config_crud.get_usdt_wallet(db)
    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pagamento em USDT não configurado no momento — contate o suporte",
        )
    wallet_address, network = wallet

    base_amount = payment_config_crud.get_usdt_amount_by_category(db, category)
    if base_amount is None or base_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Categoria {category} não tem preço em USDT configurado",
        )

    unique_amount = payment_crud.generate_unique_usdt_amount(db, base_amount)

    payment = payment_crud.create_payment(
        db,
        user_id=current_user.id,
        amount=round(base_amount, 2),
        payment_method="usdt",
        description=category,
        crypto_amount=unique_amount,
    )
    payment.payment_details = {
        "wallet_address": wallet_address,
        "network": network,
        "usdt_amount": f"{unique_amount:.6f}",
    }
    db.commit()
    db.refresh(payment)
    return payment


def _owned_payment_or_404(db: Session, current_user: User, payment_id: str) -> Payment:
    payment = payment_crud.get_by_id(db, payment_id)
    if payment is None or payment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pagamento não encontrado")
    return payment


@router.get("/{payment_id}", response_model=PaymentPublic)
async def get_payment_status(
    payment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    payment = _owned_payment_or_404(db, current_user, payment_id)

    if payment.status == "Pendente" and payment.payment_method == "usdt":
        payment = await _recheck_usdt(db, payment)
    elif payment.status == "Pendente" and payment.transaction_id:
        try:
            access_token = _get_active_access_token(db)
            mp_payment = await mercadopago_client.get_payment(access_token, payment.transaction_id)
        except (MercadoPagoError, HTTPException) as err:
            LOGGER.warning(f"Não foi possível re-checar pagamento {payment.id}: {err}")
        else:
            payment = _apply_mp_status(db, payment, mp_payment)

    return payment


async def _recheck_usdt(db: Session, payment: Payment) -> Payment:
    """Único jeito de saber que um pagamento em USDT chegou: não existe
    webhook (não há provedor terceiro) — checamos sob demanda no TronGrid
    toda vez que o painel consulta o status. Ver app/services/tron_client.py."""
    wallet = payment_config_crud.get_usdt_wallet(db)
    if wallet is None or payment.crypto_amount is None:
        return payment
    wallet_address, _network = wallet

    created_at = payment.created_at
    if created_at.tzinfo is None:
        # DATETIME do MySQL não guarda timezone — os valores que este
        # projeto grava aqui são sempre em UTC (ver app/models/base.py).
        created_at = created_at.replace(tzinfo=timezone.utc)
    since_unix_ms = int(created_at.timestamp() * 1000)
    transfer = await tron_client.find_incoming_usdt_transfer(
        wallet_address,
        expected_amount_usdt=float(payment.crypto_amount),
        since_unix_ms=since_unix_ms,
        api_key=settings.TRONGRID_API_KEY,
    )
    if transfer is not None:
        payment = payment_crud.mark_paid_and_renew(
            db, payment, transaction_id=transfer.get("transaction_id")
        )
    return payment


def _apply_mp_status(db: Session, payment: Payment, mp_payment: dict) -> Payment:
    mapped = _MP_STATUS_MAP.get(mp_payment.get("status", ""))
    if mapped == "Confirmado":
        payment = payment_crud.mark_paid_and_renew(db, payment, transaction_id=str(mp_payment.get("id")))
    elif mapped == "Cancelado":
        payment = payment_crud.mark_failed(db, payment, status="Cancelado")
    return payment


@router.post("/webhook/mercadopago", status_code=status.HTTP_200_OK)
async def mercadopago_webhook(request: Request, db: Session = Depends(get_db)):
    """Recebe notificações reais do Mercado Pago.

    Sempre responde 200 mesmo quando o pagamento local não é encontrado ou a
    consulta ao Mercado Pago falha — é o comportamento esperado por eles
    (evita reenvio agressivo); problemas ficam registrados no log.
    """
    body = await request.body()

    if settings.MERCADOPAGO_WEBHOOK_SECRET:
        if not _verify_signature(request, settings.MERCADOPAGO_WEBHOOK_SECRET):
            LOGGER.warning("Webhook do Mercado Pago com assinatura inválida — rejeitado")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura inválida")
    else:
        LOGGER.warning(
            "MERCADOPAGO_WEBHOOK_SECRET não configurado — webhook aceito sem verificar assinatura"
        )

    payment_id = _extract_payment_id(request, body)
    if not payment_id:
        LOGGER.info("Webhook do Mercado Pago sem payment id relevante — ignorado")
        return {"received": True}

    payment = payment_crud.get_by_transaction_id(db, payment_id)
    if payment is None:
        LOGGER.info(f"Webhook para pagamento {payment_id} não corresponde a nenhum registro local")
        return {"received": True}

    try:
        access_token = _get_active_access_token(db)
        mp_payment = await mercadopago_client.get_payment(access_token, payment_id)
    except (MercadoPagoError, HTTPException) as err:
        LOGGER.error(f"Falha ao consultar pagamento {payment_id} no webhook: {err}")
        return {"received": True}

    _apply_mp_status(db, payment, mp_payment)
    return {"received": True}


def _extract_payment_id(request: Request, body: bytes) -> Optional[str]:
    # Mercado Pago manda o id tanto na query string (?type=payment&data.id=123,
    # ou ?topic=payment&id=123 no formato antigo/IPN) quanto no corpo JSON
    # ({"type": "payment"|"action": "payment.*", "data": {"id": "123"}}).
    query = request.query_params
    if query.get("type") == "payment" and query.get("data.id"):
        return query.get("data.id")
    if query.get("topic") == "payment" and query.get("id"):
        return query.get("id")

    try:
        payload = json.loads(body or b"{}")
    except Exception:
        return None

    action = payload.get("action", "") or payload.get("type", "")
    if payload.get("type") == "payment" or str(action).startswith("payment."):
        data_id = payload.get("data", {}).get("id")
        return str(data_id) if data_id else None
    return None


def _verify_signature(request: Request, secret: str) -> bool:
    """Verifica o header `x-signature` do Mercado Pago.

    Formato: `ts=<timestamp>,v1=<hash>`, onde `<hash>` é o HMAC-SHA256 (chave
    = segredo do webhook configurado no painel do Mercado Pago) de
    `id:<data.id>;request-id:<x-request-id>;ts:<ts>;`.
    """
    signature_header = request.headers.get("x-signature", "")
    request_id = request.headers.get("x-request-id", "")

    parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
    ts = parts.get("ts", "")
    received_hash = parts.get("v1", "")
    if not ts or not received_hash:
        return False

    data_id = request.query_params.get("data.id") or request.query_params.get("id") or ""
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"

    expected_hash = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_hash, received_hash)
