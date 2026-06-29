"""Channel-agnostic alert dispatch.

`send_alert(job)` fans out to all configured channels and returns True iff the
PRIMARY channel delivered. Callers must mark a job 'seen' only on a True result, so
a delivery failure means the job is retried next cycle (never silently dropped).
"""

from __future__ import annotations

import logging
import os

from ..models import JobPosting
from . import formatter
from .email_sender import EmailSender
from .telegram import TelegramSender

log = logging.getLogger(__name__)


class AlertDispatcher:
    def __init__(self, *, telegram: TelegramSender | None = None,
                 email: EmailSender | None = None, dry_run: bool = False):
        self.telegram = telegram
        self.email = email
        self.dry_run = dry_run

    @classmethod
    def from_env(cls, *, dry_run: bool = False) -> "AlertDispatcher":
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        telegram = None
        if token and chat_id:
            telegram = TelegramSender(token, chat_id)
        elif not dry_run:
            log.warning("TELEGRAM_BOT_TOKEN/CHAT_ID not set — primary channel disabled.")
        email = EmailSender()
        return cls(telegram=telegram, email=email if email.enabled else None, dry_run=dry_run)

    def send_alert(self, job: JobPosting) -> bool:
        """Deliver one job. Returns True if the primary channel accepted it."""
        if self.dry_run:
            log.info("[dry-run] would alert: %s", formatter.format_plaintext(job))
            return True

        primary_ok = False
        if self.telegram is not None:
            primary_ok = self.telegram.send(formatter.format_telegram_html(job))
        else:
            log.error("No primary channel configured; cannot deliver %s", job.url)

        # Secondary (best-effort, never blocks marking-seen).
        if self.email is not None:
            self.email.send(
                subject=f"משרה חדשה באדריכלות: {job.title}",
                body=formatter.format_plaintext(job),
            )
        return primary_ok

    def send_text(self, text: str) -> bool:
        """Send a raw message (heartbeat / health alerts)."""
        if self.dry_run:
            log.info("[dry-run] would send: %s", text)
            return True
        if self.telegram is not None:
            return self.telegram.send(text, html=False, preview=False)
        return False
