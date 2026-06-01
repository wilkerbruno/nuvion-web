# backend/api/routes/payments.py
import hashlib
import hmac
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from typing import Optional

from core.security import get_current_user_id
from core.config import settings

router = APIRouter()


class PixRequest(BaseModel):
    plan: str = "Standard"   # Standard | Premium | VIP


def _payment_to_dict(p) -> dict:
    return {
        "id":             p.id,
        "amount":         float(p.amount),
        "payment_method": p.payment_method,
        "description":    p.description,
        "status":         p.status,
        "payment_date":   p.payment_date.isoformat() if p.payment_date else None,
        "due_date":       p.due_date.isoformat() if p.due_date else None,
        "transaction_id": p.transaction_id,
    }


@router.post("/pix")
def generate_pix(body: PixRequest, user_id: str = Depends(get_current_user_id)):
    """Gera cobrança PIX via Mercado Pago."""
    from crud.crud_manager import crud_system
    from core.services.payment_config_service import PaymentConfigService

    user = crud_system.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Obter valor baseado no plano
    amount = PaymentConfigService.get_amount_by_category(body.plan)
    config = PaymentConfigService.get_mercadopago_config()

    if not config.get("access_token"):
        raise HTTPException(status_code=503, detail="Pagamento não configurado")

    # Gerar PIX via Mercado Pago
    from core.services.pix_generator import PixPaymentManager
    manager = PixPaymentManager()
    result = manager.create_charge(
        amount=amount,
        customer_name=user.name,
        description=f"Assinatura {body.plan} - Nuvion Browser",
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Erro ao gerar PIX"))

    # Salvar pagamento pendente
    crud_system.payments.create(
        user_id=user_id,
        amount=amount,
        payment_method="pix",
        description=body.plan,
        status="Pendente",
        transaction_id=result.get("charge_id"),
        payment_details={"qr_code": result.get("qr_code")},
    )

    return {
        "qr_code":       result.get("qr_code"),
        "qr_code_image": result.get("qr_code_image"),
        "charge_id":     result.get("charge_id"),
        "amount":        amount,
        "plan":          body.plan,
    }


@router.get("/status/{charge_id}")
def check_status(charge_id: str, user_id: str = Depends(get_current_user_id)):
    """Consulta status do pagamento."""
    from core.services.pix_generator import PixPaymentManager
    manager = PixPaymentManager()
    result = manager.check_payment_status(charge_id)
    return result


@router.get("/history")
def payment_history(user_id: str = Depends(get_current_user_id)):
    from crud.crud_manager import crud_system
    payments = crud_system.payments.get_user_payments(user_id)
    return [_payment_to_dict(p) for p in payments]


@router.post("/webhook")
async def mercadopago_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None),
):
    """
    Webhook do Mercado Pago — confirma pagamento e ativa conta.
    https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks
    """
    body = await request.body()

    # Verificar assinatura se configurada
    if settings.MP_WEBHOOK_SECRET and x_signature:
        expected = hmac.new(
            settings.MP_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_signature.split("=")[-1]):
            raise HTTPException(status_code=401, detail="Assinatura inválida")

    data = await request.json()
    action = data.get("action", "")

    if action == "payment.updated":
        payment_id = str(data.get("data", {}).get("id", ""))
        if payment_id:
            _process_payment_confirmation(payment_id)

    return {"received": True}


def _process_payment_confirmation(mp_payment_id: str):
    """Confirma pagamento e ativa conta do usuário."""
    from crud.crud_manager import crud_system
    from core.services.payment_config_service import PaymentConfigService
    import requests

    config = PaymentConfigService.get_mercadopago_config()
    token = config.get("access_token", "")
    if not token:
        return

    try:
        r = requests.get(
            f"https://api.mercadopago.com/v1/payments/{mp_payment_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if r.status_code != 200:
            return

        mp_data = r.json()
        if mp_data.get("status") != "approved":
            return

        ext_ref = mp_data.get("external_reference", "")
        # Buscar pagamento pelo transaction_id
        payment = crud_system.payments.get_by_transaction_id(ext_ref) or \
                  crud_system.payments.get_by_transaction_id(mp_payment_id)

        if not payment:
            return

        # Confirmar pagamento
        crud_system.payments.update(payment.id, status="Confirmado", transaction_id=mp_payment_id)
        # Ativar conta do usuário
        crud_system.users.update(payment.user_id, status="Ativo")

    except Exception:
        pass
