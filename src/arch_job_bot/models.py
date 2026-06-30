"""Canonical job-posting record shared across the pipeline."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .matching.normalize import normalize


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobPosting:
    """One normalized posting. Every scraper emits these; the rest of the pipeline
    only ever sees this shape."""

    source: str                      # e.g. "alljobs"
    title: str
    url: str
    job_id: str | None = None        # stable native id when the source exposes one
    company: str | None = None
    city: str | None = None          # canonical commuter town, or raw location string
    region: str | None = None        # e.g. "דרום" / "באר שבע והסביבה"
    sub_field: str | None = None     # derived (רישוי / תכנון ערים / עיצוב פנים ...)
    posted_date: str | None = None   # normalized to dd/mm/yyyy when parseable
    salary: str | None = None
    raw_text: str = ""               # whole job-card text (dedup hash / blob fallback)
    description: str = ""            # clean JD snippet (role + duties), no card chrome
    content_hash: str | None = None
    first_seen: str = field(default_factory=_utcnow_iso)

    def full_text(self) -> str:
        """Whole-card text — kept STABLE as the dedup content-hash basis. Not used to
        decide relevance any more (that is match_text); still the geo blob fallback."""
        return " ".join(p for p in (self.title, self.company, self.raw_text) if p)

    def match_text(self) -> str:
        """Text the classifier / sub-field run against: the ROLE itself, not the whole
        card. Deliberately EXCLUDES company — an architecture firm name must not rescue
        a non-architecture role (e.g. a salesman at 'משרד אדריכלות X'). Falls back to
        raw_text when a source cannot isolate a clean snippet, so recall is preserved."""
        body = self.description or self.raw_text
        return " ".join(p for p in (self.title, body) if p)

    def compute_content_hash(self) -> str:
        """Stable hash over normalized title+company+body — the dedup fallback for
        sources without a native id, and the cross-source near-duplicate key."""
        basis = normalize(self.full_text())
        return hashlib.blake2b(basis.encode("utf-8"), digest_size=16).hexdigest()

    def ensure_hash(self) -> str:
        if not self.content_hash:
            self.content_hash = self.compute_content_hash()
        return self.content_hash

    def dedup_key(self) -> tuple[str, str]:
        """(source, key) primary identity. Prefer the native id; fall back to hash."""
        key = self.job_id if self.job_id else self.ensure_hash()
        return (self.source, str(key))
