"""Optional email channel — a free secondary delivery + permanent searchable audit log.

Disabled unless SMTP settings are present in the environment. Best-effort: a failure
here never blocks the primary (Telegram) delivery.

Env:
  ALERT_EMAIL_TO     recipient(s), comma-separated
  SMTP_HOST          e.g. smtp.gmail.com
  SMTP_PORT          e.g. 587
  SMTP_USER          login / from address
  SMTP_PASSWORD      app password (Gmail: an App Password, not the account password)
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)


class EmailSender:
    def __init__(self) -> None:
        self.to = [a.strip() for a in (os.environ.get("ALERT_EMAIL_TO") or "").split(",") if a.strip()]
        self.host = os.environ.get("SMTP_HOST")
        self.port = int(os.environ.get("SMTP_PORT") or 587)
        self.user = os.environ.get("SMTP_USER")
        self.password = os.environ.get("SMTP_PASSWORD")

    @property
    def enabled(self) -> bool:
        return bool(self.to and self.host and self.user and self.password)

    def send(self, subject: str, body: str) -> bool:
        if not self.enabled:
            return False
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.user
        msg["To"] = ", ".join(self.to)
        msg.set_content(body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as s:
                s.starttls()
                s.login(self.user, self.password)
                s.send_message(msg)
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("Email send failed (non-fatal): %s", e)
            return False
