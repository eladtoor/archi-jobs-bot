"""Geographic scope matcher — Beer Sheva commuter radius.

Two filtering modes (see plan / critique A2):
  * general high-volume boards  → geo is a HARD filter (drop out-of-scope).
  * architecture-only sources   → geo only labels; drop ONLY when a clearly
    non-commuter city is explicitly named and no in-scope signal is present.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .. import config
from .normalize import normalize


@dataclass
class GeoResult:
    city: str | None          # canonical commuter town, if matched
    region: str | None        # broad region label (e.g. "דרום"), if matched
    remote: bool
    excluded_city: str | None  # an explicit non-commuter city, if named
    raw: str = ""

    @property
    def in_scope_signal(self) -> bool:
        """Any positive reason to believe the job is reachable from Beer Sheva."""
        return bool(self.city or self.region or self.remote)

    @property
    def label(self) -> str:
        if self.city:
            return self.city
        if self.remote:
            return "מרחוק/היברידי"
        if self.region:
            return self.region
        return "לא צוין"


@lru_cache(maxsize=1)
def _geo():
    g = config.geo()
    towns = {
        canonical: [normalize(v) for v in variants]
        for canonical, variants in (g.get("commuter_towns") or {}).items()
    }
    return {
        "towns": towns,
        # (normalized-for-matching, original-for-display) so the label reads "דרום" not "דרומ"
        "regions": [(normalize(v), v) for v in (g.get("region_words") or [])],
        "remote": [normalize(v) for v in (g.get("remote_terms") or [])],
        "exclude": [normalize(v) for v in (g.get("exclude_cities") or [])],
    }


def reload() -> None:
    config.reload()
    _geo.cache_clear()


def classify_location(text: str) -> GeoResult:
    t = normalize(text)
    g = _geo()

    city = None
    for canonical, variants in g["towns"].items():
        if any(v in t for v in variants):
            city = canonical
            break

    region = next((orig for norm, orig in g["regions"] if norm in t), None)
    remote = any(r in t for r in g["remote"])
    # Only count an exclusion if it isn't actually one of our commuter towns
    # (e.g. avoid a substring surprise). Commuter match always wins.
    excluded = None
    if not city:
        excluded = next((c for c in g["exclude"] if c in t), None)

    return GeoResult(city=city, region=region, remote=remote, excluded_city=excluded, raw=text)


def passes_geo(text: str, *, location: str | None = None,
               arch_only_source: bool) -> tuple[bool, GeoResult]:
    """Decide whether a posting is in geographic scope.

    `location` is the posting's OWN parsed location field (from the source card). When
    present on a general board it is the trusted signal — we decide on it alone, far
    less noisy than the whole-card blob (which carries region menus / 'similar jobs' /
    hybrid mentions that used to leak Tel-Aviv & Lod jobs through). When absent (sources
    that don't expose a per-card location, e.g. Drushim/Maavarim) or on a label-only
    source, we fall back to the hardened blob logic below.

    arch_only_source=True  → keep unless an out-of-scope city is explicitly named
                             with no in-scope signal (recall-first for rare sources).
    arch_only_source=False → require a positive in-scope signal (commuter/region/remote).
    """
    loc = (location or "").strip()
    if loc and not arch_only_source:
        # Decide on the STATED location only. Keep the commuter ring, an explicit
        # remote/hybrid location, or a bare "דרום/נגב" region tag; drop any other named
        # city — including ones not on the finite exclude list (e.g. Lod). This is the
        # precision fix for the user's Tel-Aviv / Lod complaint.
        res = classify_location(loc)
        if res.city or res.remote or res.region:
            return True, res
        return False, res

    res = classify_location(text)
    if arch_only_source:
        # Recall-first: keep unless a non-commuter city is named with no in-scope signal.
        if res.excluded_city and not res.in_scope_signal:
            return False, res
        return True, res
    # Strict blob fallback (general board, no parsed location). A commuter city always
    # wins; an explicitly excluded city now beats a stray remote/region token elsewhere
    # in the blob (the old order let a hybrid/"דרום" mention override an excluded city);
    # otherwise remote or a region word keeps it (recall).
    if res.city:
        return True, res
    if res.excluded_city:
        return False, res
    if res.remote:
        return True, res
    return res.region is not None, res
