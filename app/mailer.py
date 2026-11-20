from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings


class Mailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, recipient: str, subject: str, markdown: str) -> None:
        if not self.settings.smtp_configured:
            raise RuntimeError("SMTP 未配置")
        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(markdown, subtype="plain", charset="utf-8")
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as smtp:
            smtp.ehlo()
            if self.settings.smtp_use_tls:
                smtp.starttls()
                smtp.ehlo()
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)
