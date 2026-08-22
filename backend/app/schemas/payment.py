"""Schemas de pagamento — checkout (PIX/cartão/USDT) e histórico."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CheckoutRequest(BaseModel):
    method: Literal["pix", "cartao", "usdt"]
    # Se omitido, usa a categoria atual do usuário (renovação). Informar
    # para fazer upgrade (ex.: Standard comprando Premium).
    category: Optional[Literal["Standard", "Premium", "VIP"]] = None

    # Obrigatórios só para "cartao" — gerado no navegador pelo Mercado
    # Pago Card Payment Brick (o backend nunca vê o número do cartão, só
    # este token). `installments`/`payment_method_id` também vêm prontos
    # do Brick (ele detecta a bandeira e o parcelamento escolhido).
    card_token: Optional[str] = None
    installments: Optional[int] = Field(default=1, ge=1, le=24)
    card_payment_method_id: Optional[str] = None
    cpf: Optional[str] = None


class PaymentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    amount: float
    crypto_amount: Optional[float] = None
    payment_method: str
    description: str
    status: str
    due_date: datetime
    payment_date: Optional[datetime] = None
    payment_details: dict
    transaction_id: Optional[str] = None
    created_at: datetime


class MercadoPagoPublicKey(BaseModel):
    public_key: str
