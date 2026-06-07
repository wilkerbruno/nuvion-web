# backend/core/services/pix_generator.py
"""
Gerador de cobranças PIX via Mercado Pago.
"""
import uuid
import requests
from utils.logger import LOGGER


class PixPaymentManager:

    def create_charge(
        self,
        amount: float,
        customer_name: str,
        description: str,
    ) -> dict:
        """Cria cobrança PIX no Mercado Pago."""
        from core.services.payment_config_service import PaymentConfigService

        config = PaymentConfigService.get_mercadopago_config()
        token = config.get("access_token", "")
        if not token:
            return {"success": False, "error": "Token Mercado Pago não configurado"}

        ext_ref = str(uuid.uuid4())
        payload = {
            "transaction_amount": float(amount),
            "description": description,
            "payment_method_id": "pix",
            "external_reference": ext_ref,
            "payer": {
                "first_name": customer_name,
                "email": f"payer_{uuid.uuid4().hex[:8]}@nuvion.app",
            },
        }

        try:
            env = config.get("environment", "sandbox")
            base = (
                "https://api.mercadopago.com"
                if env == "production"
                else "https://api.mercadopago.com"
            )
            resp = requests.post(
                f"{base}/v1/payments",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": ext_ref,
                },
                timeout=30,
            )
            data = resp.json()

            if resp.status_code in (200, 201):
                pix_info = data.get("point_of_interaction", {}).get(
                    "transaction_data", {}
                )
                return {
                    "success": True,
                    "charge_id": str(data.get("id", ext_ref)),
                    "qr_code": pix_info.get("qr_code", ""),
                    "qr_code_image": pix_info.get("qr_code_base64", ""),
                    "external_reference": ext_ref,
                }
            else:
                msg = data.get("message") or data.get("error", "Erro desconhecido")
                LOGGER.error(f"MP create_charge {resp.status_code}: {msg}")
                return {"success": False, "error": msg}

        except Exception as e:
            LOGGER.error(f"create_charge exception: {e}")
            return {"success": False, "error": str(e)}

    def check_payment_status(self, charge_id: str) -> dict:
        """Consulta status de pagamento."""
        from core.services.payment_config_service import PaymentConfigService

        config = PaymentConfigService.get_mercadopago_config()
        token = config.get("access_token", "")
        if not token:
            return {"status": "unknown", "error": "Token não configurado"}

        try:
            resp = requests.get(
                f"https://api.mercadopago.com/v1/payments/{charge_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": data.get("status", "unknown"),
                    "status_detail": data.get("status_detail", ""),
                    "charge_id": charge_id,
                }
            return {"status": "error", "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}