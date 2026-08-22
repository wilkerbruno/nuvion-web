"""Configuração de pagamento (Mercado Pago) — admin-only.

Equivalente web de core/widgets/settings/config_pagamentos_admin_section.py
no app desktop. Só administradores (`account_type == "Admin"`) podem ler ou
editar — e mesmo assim, os segredos nunca voltam em texto puro na resposta
(ver app/schemas/payment_config.py).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import settings
from app.crud import payment_config as payment_config_crud
from app.db.session import get_db
from app.models.user import User
from app.schemas.payment_config import PaymentConfigPublic, PaymentConfigUpdate, TestConnectionResult
from app.services import mercadopago_client
from app.services.mercadopago_client import MercadoPagoError

router = APIRouter(prefix="/admin/payment-config", tags=["admin"])


@router.get("", response_model=PaymentConfigPublic)
def get_payment_config(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = payment_config_crud.get_active_config(db) or payment_config_crud.get_by_key(db)
    if config is None:
        config = payment_config_crud.create_or_update(db, payment_config_crud.DEFAULT_CONFIG_KEY, {})
    return PaymentConfigPublic.from_model(config)


@router.put("", response_model=PaymentConfigPublic)
def update_payment_config(
    payload: PaymentConfigUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    config = payment_config_crud.create_or_update(db, payment_config_crud.DEFAULT_CONFIG_KEY, data)
    return PaymentConfigPublic.from_model(config)


@router.post("/test-connection", response_model=TestConnectionResult)
async def test_payment_connection(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = payment_config_crud.get_active_config(db) or payment_config_crud.get_by_key(db)
    access_token = (config.access_token if config else "") or settings.MERCADOPAGO_ACCESS_TOKEN
    if not access_token:
        return TestConnectionResult(ok=False, message="Access Token não configurado")

    try:
        ok = await mercadopago_client.test_connection(access_token)
    except MercadoPagoError as err:
        return TestConnectionResult(ok=False, message=str(err))

    if ok and config is not None:
        from datetime import datetime, timezone

        config.last_tested_at = datetime.now(timezone.utc)
        db.commit()

    return TestConnectionResult(
        ok=ok, message="Conexão realizada com sucesso!" if ok else "Falha na conexão — verifique o token"
    )
