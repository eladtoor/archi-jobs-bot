"""Per-source liveness monitoring.

With the hands-off design we have no email backbone, so a silently broken scraper is
the biggest never-miss risk: "0 new jobs" could mean a quiet market OR that AllJobs
changed its HTML and the parser now yields nothing. This monitor distinguishes them —
if a source that has historically produced postings returns 0 parsed rows (or fails to
fetch) for several consecutive cycles, it raises a one-shot alert.

State is a small JSON file in the data dir, so it survives restarts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class HealthMonitor:
    def __init__(self, state_path: str | Path, *, zero_run_threshold: int = 6,
                 fail_run_threshold: int = 4):
        self.state_path = Path(state_path)
        self.zero_threshold = zero_run_threshold      # ~6 cycles ≈ >1h at 12-min cadence
        self.fail_threshold = fail_run_threshold
        self._state = self._load()

    def _load(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                log.warning("health state unreadable; starting fresh")
        return {}

    def _save(self) -> None:
        self.state_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2),
                                   encoding="utf-8")

    def _src(self, source: str) -> dict:
        return self._state.setdefault(source, {
            "ever_had_volume": False,
            "consec_zero": 0,
            "consec_fail": 0,
            "alerted": False,
        })

    def record(self, source: str, *, fetched_ok: bool, parsed_count: int) -> str | None:
        """Record one source run. Returns an alert message string if a NEW health
        problem just crossed its threshold, else None."""
        s = self._src(source)
        alert: str | None = None

        if not fetched_ok:
            s["consec_fail"] += 1
            s["consec_zero"] = 0
        else:
            s["consec_fail"] = 0
            if parsed_count > 0:
                s["ever_had_volume"] = True
                s["consec_zero"] = 0
                if s["alerted"]:
                    s["alerted"] = False  # recovered
            else:
                s["consec_zero"] += 1

        crossed_fail = s["consec_fail"] >= self.fail_threshold
        crossed_zero = s["ever_had_volume"] and s["consec_zero"] >= self.zero_threshold
        if (crossed_fail or crossed_zero) and not s["alerted"]:
            s["alerted"] = True
            if crossed_fail:
                alert = (f"⚠️ בעיה במקור '{source}': {s['consec_fail']} ניסיונות שליפה רצופים נכשלו. "
                         f"ייתכן שהאתר חוסם או שינה מבנה.")
            else:
                alert = (f"⚠️ בעיה אפשרית במקור '{source}': {s['consec_zero']} סבבים רצופים ללא תוצאות, "
                         f"למרות שבעבר נמצאו משרות. ייתכן שהפרסר נשבר.")
        self._save()
        return alert

    def summary(self) -> str:
        """Human heartbeat summary line per source."""
        if not self._state:
            return "אין נתוני בריאות עדיין."
        parts = []
        for src, s in sorted(self._state.items()):
            flag = "🟢"
            if s.get("consec_fail", 0) >= self.fail_threshold:
                flag = "🔴"
            elif s.get("ever_had_volume") and s.get("consec_zero", 0) >= self.zero_threshold:
                flag = "🟠"
            parts.append(f"{flag} {src}")
        return " · ".join(parts)
