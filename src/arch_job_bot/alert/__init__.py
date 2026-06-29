"""Alerting: channel-agnostic dispatch (Telegram primary, email secondary)."""

from .sender import AlertDispatcher

__all__ = ["AlertDispatcher"]
