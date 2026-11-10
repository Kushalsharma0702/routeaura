from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.integrations.email.base import EmailError, EmailNotConfigured, EmailProvider


class NoEmail:
    name = "none"

    def send(self, to: str, subject: str, body: str) -> None:
        raise EmailNotConfigured("no email provider is configured (set EMAIL_PROVIDER=smtp and SMTP_HOST)")


class SmtpEmail:
    name = "smtp"

    def __init__(
        self,
        host: str,
        port: int,
        user: str | None,
        password: str | None,
        sender: str,
        starttls: bool,
        smtp_factory=smtplib.SMTP,
    ):
        self.host, self.port, self.user, self.password, self.sender, self.starttls, self._factory = (
            host,
            port,
            user,
            password,
            sender,
            starttls,
            smtp_factory,
        )

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.sender, to, subject
        msg.set_content(body)
        try:
            with self._factory(self.host, self.port, timeout=15) as smtp:
                if self.starttls:
                    smtp.starttls()
                if self.user and self.password:
                    smtp.login(self.user, self.password)
                smtp.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailError(f"smtp failed: {type(exc).__name__}") from exc


def get_email() -> EmailProvider:
    s = get_settings()
    if s.email_provider == "smtp" and s.smtp_host:
        return SmtpEmail(s.smtp_host, s.smtp_port, s.smtp_user, s.smtp_password, s.smtp_from, s.smtp_starttls)
    return NoEmail()
