"""Entry point: wires fetch → match → geo → dedup → alert, with scheduling and
the seed / dry-run / once / loop modes.

  python -m arch_job_bot.main --dry-run --once   # inspect matches, no alerts/writes
  python -m arch_job_bot.main --seed             # mark current jobs seen, no alerts
  python -m arch_job_bot.main --once             # one real cycle
  python -m arch_job_bot.main                     # run forever on the poll schedule
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from . import config
from .alert import AlertDispatcher, formatter
from .dedup import SeenStore
from .fetch.base import SourceError
from .fetch.http_client import HttpClient
from .fetch.sources import build_sources
from .health import HealthMonitor
from .matching.classifier import classify
from .matching.geo import passes_geo
from .matching.subfield import derive_subfield

log = logging.getLogger("arch_job_bot")


class Pipeline:
    def __init__(self, *, dry_run: bool = False):
        self.dry_run = dry_run
        self.http = HttpClient()
        self.sources = build_sources(self.http)
        self.store = SeenStore(config.data_dir() / "seen_jobs.sqlite3")
        self.dispatcher = AlertDispatcher.from_env(dry_run=dry_run)
        self.health = HealthMonitor(config.data_dir() / "health.json")

    # ── match + geo + enrich, per source ─────────────────────────────────────
    def _candidates(self):
        """Yield enriched postings that pass the classifier and the geo gate."""
        for source in self.sources:
            try:
                postings = source.fetch()
            except SourceError as e:
                log.warning("%s", e)
                msg = self.health.record(source.name, fetched_ok=False, parsed_count=0)
                if msg:
                    self.dispatcher.send_text(msg)
                continue

            matched = []
            for p in postings:
                text = p.full_text()
                if not classify(text).accepted:
                    continue
                ok_geo, geo_res = passes_geo(text, arch_only_source=source.geo_label_only)
                if not ok_geo:
                    continue
                p.sub_field = derive_subfield(text)
                p.city = geo_res.city or p.city or geo_res.label
                if geo_res.region and not p.region:
                    p.region = geo_res.region
                matched.append(p)

            log.info("%s: fetched=%d matched-in-scope=%d", source.name, len(postings), len(matched))
            msg = self.health.record(source.name, fetched_ok=True, parsed_count=len(postings))
            if msg:
                self.dispatcher.send_text(msg)
            for p in matched:
                yield source.name, p

    # ── modes ────────────────────────────────────────────────────────────────
    def _new_sources(self) -> set[str]:
        """On a populated DB, sources with zero stored rows are brand-new → their first
        cycle is seeded silently (no backlog flood). On an empty DB the global seed runs."""
        if self.dry_run or self.store.count() == 0:
            return set()
        new = {s.name for s in self.sources if self.store.count_by_source(s.name) == 0}
        if new:
            log.info("new source(s) will be silently seeded this cycle (no alerts): %s", new)
        return new

    def run_cycle(self) -> int:
        alerted = 0
        new_sources = self._new_sources()
        for source_name, p in self._candidates():
            if source_name in new_sources:
                self.store.record(p)          # seed a brand-new source, no alert
                continue
            if not self.store.is_new(p):
                continue
            if self.dry_run:
                print(formatter.format_plaintext(p))
                print("-" * 60)
                alerted += 1
                continue
            # Invariant: persist as seen ONLY after a successful delivery.
            if self.dispatcher.send_alert(p):
                self.store.record(p)
                alerted += 1
            else:
                log.warning("delivery failed; will retry next cycle: %s", p.url)
        log.info("cycle complete: %d new alert(s)", alerted)
        return alerted

    def seed(self) -> int:
        """Mark all current matches as seen WITHOUT alerting (silent first-run seed)."""
        seeded = sum(1 for _src, p in self._candidates() if self.store.record(p))
        log.info("seed complete: %d job(s) marked seen (no alerts)", seeded)
        return seeded

    def weekly_digest(self) -> None:
        from .alert.digest import format_weekly_digest
        counts = self.store.digest_counts(7)
        self.dispatcher.send_user(format_weekly_digest(counts))
        log.info("weekly digest sent: %d job(s) in last 7d", counts.get("total", 0))

    def heartbeat(self) -> None:
        total = self.store.count()
        text = (f"🤖 בוט המשרות פעיל. מקורות: {self.health.summary()}. "
                f"סה\"כ משרות שנראו עד כה: {total}.")
        self.dispatcher.send_text(text)

    def close(self) -> None:
        self.http.close()
        self.store.close()


def _run_scheduler(pipe: Pipeline, interval: int) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler

    sched = BlockingScheduler()
    sched.add_job(pipe.run_cycle, "interval", minutes=interval,
                  next_run_time=datetime.now(), jitter=60,
                  id="poll", max_instances=1, coalesce=True)
    sched.add_job(pipe.heartbeat, "cron", hour=9, minute=0, id="heartbeat")
    sched.add_job(pipe.weekly_digest, "cron", day_of_week="sun", hour=9, minute=5, id="weekly")
    log.info("scheduler started: polling every %d min (+jitter), heartbeat 09:00, digest Sun 09:05",
             interval)
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler stopped")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Architecture job-alert bot (Beer Sheva / South)")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--seed", action="store_true", help="mark current jobs seen, no alerts")
    parser.add_argument("--dry-run", action="store_true", help="classify and print, no alerts/writes")
    parser.add_argument("--no-seed", action="store_true", help="skip the auto-seed on first (empty) run")
    parser.add_argument("--interval", type=int, default=None, help="poll interval minutes (override)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    # Hebrew/emoji output must not die on a legacy console codepage (e.g. Windows cp1255).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:  # noqa: BLE001
        pass

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    interval = args.interval or int(config.sources().get("poll_minutes_default", 12))
    pipe = Pipeline(dry_run=args.dry_run)
    try:
        if args.seed:
            pipe.seed()
            return 0

        # First-ever run on an empty DB → silent seed so day 1 isn't a flood.
        if not args.dry_run and not args.no_seed and pipe.store.count() == 0:
            log.info("empty dedup DB → performing a silent seed run (no alerts)")
            pipe.seed()
            if args.once:
                return 0

        if args.dry_run or args.once:
            pipe.run_cycle()
            return 0

        _run_scheduler(pipe, interval)
        return 0
    finally:
        pipe.close()


if __name__ == "__main__":
    raise SystemExit(main())
