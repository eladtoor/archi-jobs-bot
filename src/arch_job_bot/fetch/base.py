"""Base class and helpers for source scrapers."""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from ..models import JobPosting

log = logging.getLogger(__name__)


class SourceError(Exception):
    """Raised by a scraper when it cannot produce results (network/parse failure)."""


class BaseSource:
    name: str = "base"
    arch_only: bool = False           # architecture-only board → geo only labels
    geo_trusted: bool = False          # query already narrowed to the BS area → geo only labels
    poll_minutes: int = 12            # desired cadence

    def __init__(self, http, queries: list[str] | None = None,
                 *, arch_only: bool | None = None, geo_trusted: bool | None = None,
                 poll_minutes: int | None = None):
        self.http = http
        self.queries = queries or []
        if arch_only is not None:
            self.arch_only = arch_only
        if geo_trusted is not None:
            self.geo_trusted = geo_trusted
        if poll_minutes is not None:
            self.poll_minutes = poll_minutes

    @property
    def geo_label_only(self) -> bool:
        """If True, geo only labels (never drops on a missing in-scope signal)."""
        return self.arch_only or self.geo_trusted

    def fetch(self) -> list[JobPosting]:
        """Fetch + parse every configured query URL. Resilient: one failing query
        does not sink the others. Raises SourceError only if EVERY query failed to
        fetch (so the health monitor can tell 'broken' from 'quiet')."""
        out: list[JobPosting] = []
        fetched_any = False
        for url in self.queries:
            html = self.http.get_text(url)
            if html is None:
                continue
            fetched_any = True
            try:
                out.extend(self.parse(html, url))
            except Exception as e:  # noqa: BLE001 — a parser bug must not crash the loop
                log.warning("%s: parse failed for %s: %s", self.name, url, e)
        if self.queries and not fetched_any:
            raise SourceError(f"{self.name}: all {len(self.queries)} queries failed to fetch")
        return out

    def parse(self, html: str, url: str) -> list[JobPosting]:  # pragma: no cover - overridden
        raise NotImplementedError


# ── shared parsing helpers ───────────────────────────────────────────────────

_REL_RE = re.compile(r"לפני\s+(\d+)\s*(דקות|דקה|שעות|שעה|שעתיים|ימים|יום|יומיים|שבוע|שבועות|חודש)")


def normalize_posted_date(raw: str | None, today: date | None = None) -> str | None:
    """Convert a relative Hebrew date ('פורסם לפני 15 דקות', 'לפני 3 ימים') or an
    absolute dd/mm/yyyy string into a stable dd/mm/yyyy string. Unknown → cleaned raw."""
    if not raw:
        return None
    raw = raw.strip()
    today = today or date.today()

    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", raw)
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = "20" + y
        return f"{int(d):02d}/{int(mo):02d}/{y}"

    rel = _REL_RE.search(raw)
    if rel:
        n = int(rel.group(1))
        unit = rel.group(2)
        if unit in ("דקות", "דקה", "שעות", "שעה", "שעתיים"):
            return today.strftime("%d/%m/%Y")              # today
        if unit in ("ימים", "יום"):
            return (today - timedelta(days=n)).strftime("%d/%m/%Y")
        if unit == "יומיים":
            return (today - timedelta(days=2)).strftime("%d/%m/%Y")
        if unit in ("שבוע", "שבועות"):
            return (today - timedelta(weeks=n)).strftime("%d/%m/%Y")
        if unit == "חודש":
            return (today - timedelta(days=30)).strftime("%d/%m/%Y")

    if "היום" in raw:
        return today.strftime("%d/%m/%Y")
    if "אתמול" in raw:
        return (today - timedelta(days=1)).strftime("%d/%m/%Y")
    return raw[:40] or None


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()
