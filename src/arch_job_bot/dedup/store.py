"""Grow-only SQLite dedup store.

Two invariants make the bot never-miss AND never-duplicate:
  1. A row is written ONLY AFTER an alert was successfully delivered — so a crash
     mid-cycle just retries next cycle instead of silently swallowing the job.
  2. The store is append-only (never pruned) — a reposted job with the same id
     won't re-alert, and an old id can't be forgotten and re-fired.

Dedup identity is (source, key) where key is the source's stable native id, or a
content hash when the source exposes no id. Cross-source suppression is deliberately
conservative (exact normalized-text hash only) to avoid collapsing two distinct
openings from the same employer (critique A4 — bias toward under-deduping).
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..matching.normalize import normalize
from ..models import JobPosting

# Cross-source suppression: only for titles specific enough to be safe (short generic
# titles like "אדריכל/ית" must never collapse two distinct roles — never-miss bias).
_CROSS_MIN_TITLE_LEN = 25
_CROSS_WINDOW_DAYS = 14

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    source       TEXT NOT NULL,
    job_id       TEXT NOT NULL,     -- resolved dedup key (native id or content hash)
    url          TEXT,
    content_hash TEXT,
    title        TEXT,
    sub_field    TEXT,
    sig          TEXT,              -- normalize(title)|city — cross-source repost key
    first_seen   TIMESTAMP NOT NULL,
    PRIMARY KEY (source, job_id)
);
CREATE INDEX IF NOT EXISTS idx_seen_hash ON seen_jobs (content_hash);
"""
# (the sig index is created in _migrate, AFTER the column is ensured on legacy DBs)


def _sig(posting: JobPosting) -> str:
    return normalize(posting.title) + "|" + normalize(posting.city or "")


class SeenStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Add v2 columns to a pre-existing (prod) DB that lacks them."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(seen_jobs)").fetchall()}
        for col in ("sub_field", "sig"):
            if col not in cols:
                self._conn.execute(f"ALTER TABLE seen_jobs ADD COLUMN {col} TEXT")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_sig ON seen_jobs (sig)")

    # ── queries ──────────────────────────────────────────────────────────────
    def is_new(self, posting: JobPosting, *, cross_source: bool = True) -> bool:
        """True if we have not alerted on this posting before.

        Primary identity is (source, job_id). When cross_source=True (default), also
        suppress a posting whose specific title+city was already alerted from a
        DIFFERENT source within the last 14 days — so the same municipal job appearing
        on muni + Maavarim + AllJobs fires once. Short/generic titles are never
        cross-suppressed (never-miss bias)."""
        source, key = posting.dedup_key()
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM seen_jobs WHERE source = ? AND job_id = ? LIMIT 1",
                (source, key),
            ).fetchone()
            if row is not None:
                return False
            if cross_source and len(normalize(posting.title)) >= _CROSS_MIN_TITLE_LEN:
                cutoff = (datetime.now(timezone.utc) - timedelta(days=_CROSS_WINDOW_DAYS)).isoformat()
                dup = self._conn.execute(
                    "SELECT 1 FROM seen_jobs WHERE sig = ? AND source != ? AND first_seen >= ? LIMIT 1",
                    (_sig(posting), source, cutoff),
                ).fetchone()
                if dup is not None:
                    return False
        return True

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]

    def count_by_source(self, source: str) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM seen_jobs WHERE source = ?", (source,)
            ).fetchone()[0]

    def digest_counts(self, days: int = 7) -> dict:
        """Counts of jobs first seen in the last `days`, for the weekly digest."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM seen_jobs WHERE first_seen >= ?", (cutoff,)
            ).fetchone()[0]
            by_sub = self._conn.execute(
                "SELECT COALESCE(sub_field,'אחר'), COUNT(*) FROM seen_jobs "
                "WHERE first_seen >= ? GROUP BY sub_field ORDER BY 2 DESC", (cutoff,)
            ).fetchall()
            by_src = self._conn.execute(
                "SELECT source, COUNT(*) FROM seen_jobs "
                "WHERE first_seen >= ? GROUP BY source ORDER BY 2 DESC", (cutoff,)
            ).fetchall()
        return {"days": days, "total": total,
                "by_subfield": dict(by_sub), "by_source": dict(by_src)}

    # ── writes (call ONLY after successful delivery, or during seed) ──────────
    def record(self, posting: JobPosting) -> bool:
        """Persist the posting as seen. Returns True if a new row was inserted.
        Idempotent via INSERT OR IGNORE on the (source, job_id) primary key."""
        source, key = posting.dedup_key()
        h = posting.ensure_hash()
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO seen_jobs "
                "(source, job_id, url, content_hash, title, sub_field, sig, first_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (source, key, posting.url, h, posting.title,
                 posting.sub_field, _sig(posting), posting.first_seen),
            )
            self._conn.commit()
            return cur.rowcount == 1

    def seed(self, postings: list[JobPosting]) -> int:
        """Silently mark a batch as seen WITHOUT alerting (first-run seed)."""
        n = 0
        for p in postings:
            if self.record(p):
                n += 1
        return n

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "SeenStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
