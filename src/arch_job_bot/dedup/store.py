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
from pathlib import Path

from ..models import JobPosting

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    source       TEXT NOT NULL,
    job_id       TEXT NOT NULL,     -- resolved dedup key (native id or content hash)
    url          TEXT,
    content_hash TEXT,
    title        TEXT,
    first_seen   TIMESTAMP NOT NULL,
    PRIMARY KEY (source, job_id)
);
CREATE INDEX IF NOT EXISTS idx_seen_hash ON seen_jobs (content_hash);
"""


class SeenStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ── queries ──────────────────────────────────────────────────────────────
    def is_new(self, posting: JobPosting, *, cross_source: bool = False) -> bool:
        """True if we have not alerted on this posting before.

        cross_source=True also suppresses an exact-text duplicate already seen on a
        *different* board (conservative: identical normalized text only)."""
        source, key = posting.dedup_key()
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM seen_jobs WHERE source = ? AND job_id = ? LIMIT 1",
                (source, key),
            ).fetchone()
            if row is not None:
                return False
            if cross_source:
                h = posting.ensure_hash()
                dup = self._conn.execute(
                    "SELECT 1 FROM seen_jobs WHERE content_hash = ? LIMIT 1", (h,)
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

    # ── writes (call ONLY after successful delivery, or during seed) ──────────
    def record(self, posting: JobPosting) -> bool:
        """Persist the posting as seen. Returns True if a new row was inserted.
        Idempotent via INSERT OR IGNORE on the (source, job_id) primary key."""
        source, key = posting.dedup_key()
        h = posting.ensure_hash()
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO seen_jobs "
                "(source, job_id, url, content_hash, title, first_seen) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source, key, posting.url, h, posting.title, posting.first_seen),
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
