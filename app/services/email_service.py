"""Email service for sending transactional emails (e.g. password reset)."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self) -> None:
        """Initialize email service with settings."""
        self.settings = get_settings()

    def is_configured(self) -> bool:
        """Check if SMTP is configured for sending emails."""
        return bool(self.settings.smtp_host and self.settings.smtp_user and self.settings.smtp_password)

    def send_password_reset_email(self, to_email: str, reset_link: str, user_name: str | None = None) -> bool:
        """
        Send password reset email to user.

        Args:
            to_email: Recipient email address
            reset_link: Full URL for password reset (includes token)
            user_name: Optional user name for personalization

        Returns:
            True if email was sent (or logged in dev), False on failure
        """
        subject = "Redefinição de senha - CRM Imobiliário com IA - Desafio Astrocode"
        greeting = f"Olá, {user_name}!" if user_name else "Olá!"
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #1976d2;">Redefinição de senha</h2>
                <p>{greeting}</p>
                <p>Você solicitou a redefinição de senha para sua conta no CRM Imobiliário.</p>
                <p>Clique no botão abaixo para criar uma nova senha:</p>
                <p style="margin: 30px 0;">
                    <a href="{reset_link}" style="background-color: #1976d2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                        Redefinir senha
                    </a>
                </p>
                <p>Ou copie e cole o link no navegador:</p>
                <p style="word-break: break-all; color: #666; font-size: 12px;">{reset_link}</p>
                <p style="margin-top: 30px; color: #999; font-size: 12px;">
                    Este link expira em 1 hora. Se você não solicitou esta alteração, ignore este e-mail.
                </p>
            </div>
        </body>
        </html>
        """
        body_text = f"""
        {greeting}

        Você solicitou a redefinição de senha para sua conta no CRM Imobiliário.

        Acesse o link abaixo para criar uma nova senha:
        {reset_link}

        Este link expira em 1 hora. Se você não solicitou esta alteração, ignore este e-mail.
        """

        if not self.is_configured():
            logger.info(
                "SMTP not configured. Password reset link (dev mode): %s",
                reset_link,
            )
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.settings.smtp_from_email
            msg["To"] = to_email

            msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
                if self.settings.smtp_use_tls:
                    server.starttls()
                server.login(self.settings.smtp_user, self.settings.smtp_password)
                server.sendmail(self.settings.smtp_from_email, to_email, msg.as_string())

            logger.info("Password reset email sent successfully to %s", to_email)
            return True
        except Exception as e:
            logger.exception("Failed to send password reset email: %s", e)
            return False
