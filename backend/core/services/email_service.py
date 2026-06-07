# backend/core/services/email_service.py
"""
Serviço de e-mail para o backend web.
Envia e-mails transacionais (recuperação de senha, boas-vindas, etc).
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.logger import LOGGER


class EmailService:

    def _get_smtp_config(self) -> dict:
        try:
            from utils.config_manager import config_manager
            c = config_manager.load_smtp_config()
            return {
                "host":     c.smtp_host,
                "port":     c.smtp_port,
                "email":    c.smtp_email,
                "password": c.smtp_password,
                "use_tls":  c.smtp_use_tls,
                "sender":   c.sender_name,
            }
        except Exception:
            from core.config import settings
            return {
                "host":     "smtp.gmail.com",
                "port":     587,
                "email":    "",
                "password": "",
                "use_tls":  True,
                "sender":   "Nuvion Browser",
            }

    def send_recovery_email(
        self, to_email: str, user_name: str, token: str
    ) -> bool:
        """Envia e-mail de recuperação de senha."""
        cfg = self._get_smtp_config()
        if not cfg["email"] or not cfg["password"]:
            LOGGER.warning("SMTP não configurado — e-mail de recuperação não enviado")
            return False

        subject = "Recuperação de senha — Nuvion Browser"
        body = f"""
        <p>Olá, <strong>{user_name}</strong>!</p>
        <p>Você solicitou a recuperação de senha.</p>
        <p>Use o código abaixo (válido por 15 minutos):</p>
        <h2 style="letter-spacing:4px">{token}</h2>
        <p>Se não foi você, ignore este e-mail.</p>
        <p>— Equipe Nuvion Browser</p>
        """
        return self._send(cfg, to_email, subject, body)

    def _send(self, cfg: dict, to: str, subject: str, html_body: str) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{cfg['sender']} <{cfg['email']}>"
            msg["To"] = to
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
                if cfg["use_tls"]:
                    server.starttls()
                server.login(cfg["email"], cfg["password"])
                server.sendmail(cfg["email"], to, msg.as_string())

            LOGGER.info(f"E-mail enviado para {to}: {subject}")
            return True
        except Exception as e:
            LOGGER.error(f"Falha ao enviar e-mail para {to}: {e}")
            return False


email_service = EmailService()