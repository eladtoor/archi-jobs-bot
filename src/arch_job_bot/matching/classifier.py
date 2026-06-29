"""Recall-first architecture-job classifier.

Given a posting's text, decide whether it is a relevant architecture role. The
guiding rule is the user's #1 requirement: NEVER miss a real job — so we accept on
any strong building signal and reject only when a hard gate clearly fires (software
"architect", pure structural engineering, real-estate sales, non-arch drafting).

Pure functions, fully unit-testable offline (see tests/test_classifier.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from .. import config
from .normalize import normalize


@dataclass
class Classification:
    accepted: bool
    reason: str                       # human-readable why (for logs/debugging)
    matched: list[str] = field(default_factory=list)   # positive terms that hit

    def __bool__(self) -> bool:       # `if classify(text):`
        return self.accepted


@lru_cache(maxsize=1)
def _kw() -> dict[str, list[str]]:
    """Keyword lists, normalized once so both sides of the substring test agree."""
    raw = config.keywords()
    out: dict[str, list[str]] = {}
    for key, val in raw.items():
        if isinstance(val, list):
            out[key] = [normalize(str(v)) for v in val]
    return out


def reload() -> None:
    config.reload()
    _kw.cache_clear()


def _hits(terms: list[str], text: str) -> list[str]:
    return [t for t in terms if t and t in text]


def classify(text: str) -> Classification:
    """Classify a posting's combined text. Order matters: rejection gates run before
    acceptance so an explicit software/sales/structural signal wins."""
    t = normalize(text)
    kw = _kw()

    arch_word = _hits(kw.get("arch_word_forms", []), t)
    role_title = _hits(kw.get("role_titles", []), t)
    permit = _hits(kw.get("permit_jargon", []), t)
    adjacent = _hits(kw.get("adjacent_positive", []), t)
    eng_title = _hits(kw.get("english_titles", []), t)
    ambiguous = _hits(kw.get("ambiguous_terms", []), t)

    # A genuine building-architecture signal (drives both acceptance and gate exceptions).
    building_signal = arch_word + role_title + permit + adjacent
    # A building role specifically (used so a stray "מערכת" doesn't reject a real arch post).
    building_role = arch_word + role_title + permit
    # Building context INDEPENDENT of the bare arch word — because "אדריכל תוכנה" has the
    # arch word but is software; a real building post also carries a permit/role/adjacent term.
    strong_building = role_title + permit + adjacent

    # ── Gate 1: explicit software-architect TITLES ───────────────────────────────
    reject_titles = _hits(kw.get("reject_software_titles", []), t)
    if reject_titles and not strong_building:
        return Classification(False, f"tech: software-architect title {reject_titles}")

    # ── Gate 2: ambiguous "ארכיטקט/architect" in a tech context, no building signal ─
    tech_qual = _hits(kw.get("tech_qualifiers", []), t)
    tech_stack = _hits(kw.get("tech_stack", []), t)
    if ambiguous and not arch_word and not building_signal:
        if reject_titles or tech_qual or tech_stack:
            return Classification(False, "tech: ambiguous architect + tech context")

    # ── Gate 3: real-estate sales with no design role ───────────────────────────
    sales = _hits(kw.get("sales_terms", []), t)
    if sales and not building_signal:
        return Classification(False, f"sales: {sales}")

    # ── Gate 4: pure structural engineering (kept if אדריכל is also sought) ──────
    structural = _hits(kw.get("structural_terms", []), t)
    if structural and not building_signal:
        return Classification(False, f"structural-only: {structural}")

    # ── Gate 5: non-architectural drafting (electrical/plumbing/HVAC), drafting-only
    # `adjacent` such as שרטט/שרטוט with a non-arch domain word and no arch role → reject.
    drafting_domains = _hits(kw.get("non_arch_drafting_domains", []), t)
    if adjacent and drafting_domains and not building_role:
        return Classification(False, f"non-arch drafting domain: {drafting_domains}")

    # ── Acceptance (recall-first) ───────────────────────────────────────────────
    if building_signal:
        return Classification(True, "building signal", sorted(set(building_signal)))
    if eng_title:
        return Classification(True, "english title", sorted(set(eng_title)))
    if ambiguous:
        coterms = _hits(kw.get("building_coterms", []), t)
        if coterms and not (tech_qual or tech_stack):
            return Classification(True, "ambiguous architect + building co-term", ambiguous)

    # Software tokens alone are NOT sufficient.
    return Classification(False, "no strong architecture signal")
