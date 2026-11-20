from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from .config import Settings


@dataclass(frozen=True)
class EmailConfig:
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    sender: str = ""
    use_tls: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.host and self.sender)

    @classmethod
    def from_settings(cls, settings: Settings) -> "EmailConfig":
        return cls(settings.smtp_host, settings.smtp_port, settings.smtp_username, settings.smtp_password, settings.smtp_from, settings.smtp_use_tls)

    @classmethod
    def from_row(cls, row: dict) -> "EmailConfig":
        return cls(row["host"], row["port"], row["username"], row["password"], row["sender"], bool(row["use_tls"]))


class Mailer:
    def __init__(self, settings: Settings):
        self.default_config = EmailConfig.from_settings(settings)

    def send(self, recipient: str, subject: str, markdown: str, config: EmailConfig | None = None) -> None:
        config = config or self.default_config
        if not config.configured:
            raise RuntimeError("SMTP 未配置")
        message = EmailMessage()
        message["From"] = config.sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(markdown, subtype="plain", charset="utf-8")
        with smtplib.SMTP(config.host, config.port, timeout=20) as smtp:
            smtp.ehlo()
            if config.use_tls:
                smtp.starttls()
                smtp.ehlo()
            if config.username:
                smtp.login(config.username, config.password)
            smtp.send_message(message)
