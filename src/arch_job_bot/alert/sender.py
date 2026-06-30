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
                 admin: TelegramSender | None = None,
                 email: EmailSender | None = None, dry_run: bool = False):
        self.telegram = telegram          # jobs + weekly digest → Karin
        self.admin = admin                # health / heartbeat / errors → Elad
        self.email = email
        self.dry_run = dry_run

    @classmethod
    def from_env(cls, *, dry_run: bool = False) -> "AlertDispatcher":
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")           # Karin (jobs)
        admin_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID") or chat_id  # Elad (ops); falls back to jobs
        telegram = TelegramSender(token, chat_id) if token and chat_id else None
        admin = TelegramSender(token, admin_id) if token and admin_id else None
        if telegram is None and not dry_run:
            log.warning("TELEGRAM_BOT_TOKEN/CHAT_ID not set — primary channel disabled.")
        if admin_id == chat_id and not dry_run:
            log.warning("TELEGRAM_ADMIN_CHAT_ID not set — ops messages go to Karin's chat.")
        email = EmailSender()
        return cls(telegram=telegram, admin=admin,
                   email=email if email.enabled else None, dry_run=dry_run)

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
        """Ops message (heartbeat / health / source-down / errors) → admin chat (Elad)."""
        if self.dry_run:
            log.info("[dry-run] would send OPS: %s", text)
            return True
        if self.admin is not None:
            return self.admin.send(text, html=False, preview=False)
        return False

    def send_user(self, text: str, *, html: bool = True) -> bool:
        """User-facing message (e.g. weekly digest) → Karin's jobs chat."""
        if self.dry_run:
            log.info("[dry-run] would send to Karin: %s", text)
            return True
        if self.telegram is not None:
            return self.telegram.send(text, html=html, preview=False)
        return False
