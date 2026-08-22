"""Parser/validador de cookies de sessão de IA (Fase 4).

Portado e consolidado de dois módulos do app desktop que faziam quase a
mesma coisa (`core/utils/cookie_parser.py` e `core/utils/cookie_helper.py`)
— aqui viram um só, `CookieParser`, com os métodos realmente usados pelo
backend: normalização/validação de cookies exportados de extensões
(EditThisCookie, Cookie-Editor, Chrome DevTools) e extração de domínio para
metadados (`app/models/ai_session_cookies.py::_update_metadata`, que ficou
com esse import como TODO pendente desde a Fase 0 até agora).
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


class CookieParser:
    """Normalização e validação de cookies de sessão exportados por extensões."""

    @staticmethod
    def parse_cookies_from_json_string(json_string: str) -> List[Dict]:
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError:
            return []
        return CookieParser._normalize(data)

    @staticmethod
    def validate_cookies_data(cookies_raw) -> Tuple[bool, str, List[Dict]]:
        """Aceita tanto uma string JSON quanto uma lista já parseada
        (a API recebe JSON de verdade, o app desktop recebia texto colado)."""
        if isinstance(cookies_raw, str):
            if not cookies_raw.strip():
                return False, "Dados de cookies vazios", []
            try:
                data = json.loads(cookies_raw)
            except json.JSONDecodeError as e:
                return False, f"JSON inválido: {e}", []
        else:
            data = cookies_raw

        normalized = CookieParser._normalize(data)
        if not normalized:
            return False, "Nenhum cookie válido encontrado", []
        return True, f"{len(normalized)} cookies válidos", normalized

    @staticmethod
    def _normalize(data) -> List[Dict]:
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return []

        normalized = []
        for cookie in data:
            if not isinstance(cookie, dict):
                continue
            if not cookie.get("name") or not cookie.get("value"):
                continue
            normalized.append(
                {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain", ""),
                    "path": cookie.get("path", "/"),
                    "secure": cookie.get("secure", False),
                    "httpOnly": cookie.get("httpOnly", False),
                    "sameSite": cookie.get("sameSite", "Lax"),
                    "expirationDate": CookieParser._parse_expiration(cookie),
                    "hostOnly": cookie.get("hostOnly", False),
                    "session": cookie.get("session", False),
                }
            )
        return normalized

    @staticmethod
    def _parse_expiration(cookie: Dict) -> Optional[float]:
        exp_date = cookie.get("expirationDate")
        if isinstance(exp_date, (int, float)):
            return float(exp_date)

        expires = cookie.get("expires")
        if isinstance(expires, (int, float)):
            return float(expires)
        if isinstance(expires, str):
            try:
                return datetime.fromisoformat(expires.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return None

        return None

    @staticmethod
    def extract_domain_from_cookies(cookies: List[Dict]) -> Optional[str]:
        try:
            for cookie in cookies or []:
                domain = (cookie.get("domain") or "").strip().lstrip(".")
                if domain:
                    return domain
            return None
        except Exception:
            return None

    @staticmethod
    def calculate_expiration(cookies: List[Dict]) -> Optional[datetime]:
        min_expiration = None
        for cookie in cookies or []:
            exp_date = cookie.get("expirationDate")
            if not isinstance(exp_date, (int, float)):
                continue
            exp_dt = datetime.fromtimestamp(exp_date, tz=timezone.utc)
            if min_expiration is None or exp_dt < min_expiration:
                min_expiration = exp_dt
        return min_expiration
