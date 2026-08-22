"""Cliente da API pública do TronGrid — usado só para LER a blockchain
Tron (checar se uma transferência USDT-TRC20 chegou na carteira
configurada). O backend nunca guarda nem usa uma chave privada — não
assina nem envia transação nenhuma. A carteira que recebe os pagamentos é
de propriedade da Divisions Tech, gerenciada fora deste sistema (ex.:
TronLink, Ledger); ver docs/PAGAMENTOS_CRIPTO.md para o desenho completo.

Endereço do contrato oficial do USDT na rede Tron (TRC20), confirmado em
tether.to e no TronScan: TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t. USDT usa 6
casas decimais nessa rede (diferente das 2 casas do BRL).
"""
from typing import Optional

import httpx

from app.core.logging import LOGGER

TRONGRID_API_BASE_URL = "https://api.trongrid.io"
USDT_TRC20_CONTRACT_ADDRESS = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
USDT_DECIMALS = 6
_REQUEST_TIMEOUT_SECONDS = 15.0

# Metade da menor unidade de USDT (0.000001) — tolerância pra comparação de
# ponto flutuante, não pra aceitar valores "quase certos": os valores que
# geramos em app/crud/payment.py já são exclusivos até a 6ª casa decimal.
_AMOUNT_TOLERANCE = 0.0000005


async def find_incoming_usdt_transfer(
    wallet_address: str,
    expected_amount_usdt: float,
    since_unix_ms: int,
    api_key: str = "",
) -> Optional[dict]:
    """Procura, nas transferências TRC20 recebidas por `wallet_address`
    desde `since_unix_ms`, uma no valor de `expected_amount_usdt`. Retorna
    o dict cru da transferência (do TronGrid) se achar, `None` caso
    contrário — inclusive em caso de erro de rede/API (quem chama trata
    igual a "ainda não confirmado", o mesmo padrão já usado pra falha
    pontual ao re-checar um pagamento no Mercado Pago).
    """
    headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
    params = {
        "only_confirmed": "true",
        "only_to": "true",
        "limit": 50,
        "contract_address": USDT_TRC20_CONTRACT_ADDRESS,
        "min_timestamp": since_unix_ms,
    }
    url = f"{TRONGRID_API_BASE_URL}/v1/accounts/{wallet_address}/transactions/trc20"

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        LOGGER.warning(f"Falha ao consultar TronGrid para {wallet_address}: {e}")
        return None

    for transfer in data.get("data", []):
        if transfer.get("to") != wallet_address:
            continue
        try:
            raw_value = int(transfer.get("value", "0"))
        except (TypeError, ValueError):
            continue
        amount = raw_value / (10**USDT_DECIMALS)
        if abs(amount - expected_amount_usdt) <= _AMOUNT_TOLERANCE:
            return transfer

    return None
