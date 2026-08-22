"""Constantes usadas nos modelos (portado 1:1 de database/models/constants.py)."""


class BlockReasons:
    """Motivos padronizados para bloqueio de usuários."""

    NEW_DEVICE = "Tentativa de login em dispositivo não autorizado"
    PAYMENT_OVERDUE = "Pagamento em atraso - renove sua assinatura"
    ADMIN_ACTION = "Conta bloqueada por administrador"
    SECURITY_VIOLATION = "Atividade suspeita detectada"
    MULTIPLE_FAILED_LOGINS = "Múltiplas tentativas de login falhadas"
    USER_REQUEST = "Bloqueio solicitado pelo usuário"

    @classmethod
    def get_all(cls):
        return {
            "new_device": cls.NEW_DEVICE,
            "payment_overdue": cls.PAYMENT_OVERDUE,
            "admin_action": cls.ADMIN_ACTION,
            "security_violation": cls.SECURITY_VIOLATION,
            "multiple_failed_logins": cls.MULTIPLE_FAILED_LOGINS,
            "user_request": cls.USER_REQUEST,
        }

    @classmethod
    def get_choices(cls):
        return [
            ("new_device", "Dispositivo não autorizado"),
            ("payment_overdue", "Pagamento em atraso"),
            ("admin_action", "Ação administrativa"),
            ("security_violation", "Violação de segurança"),
            ("multiple_failed_logins", "Múltiplas falhas de login"),
            ("user_request", "Solicitação do usuário"),
        ]


class AuthorizationStatus:
    """Status de autorização de dispositivos."""

    PENDING = "pending"
    AUTHORIZED = "authorized"
    REJECTED = "rejected"

    @classmethod
    def get_all(cls):
        return [cls.PENDING, cls.AUTHORIZED, cls.REJECTED]
