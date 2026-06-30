"""v2 infra tests: ISO dates, procurement gate, far-Negev geo, cross-source dedup,
challenge guard, per-source counts, weekly digest."""

from arch_job_bot.alert.digest import format_weekly_digest
from arch_job_bot.dedup import SeenStore
from arch_job_bot.fetch.base import normalize_posted_date
from arch_job_bot.fetch.http_client import _is_challenge
from arch_job_bot.matching.classifier import classify
from arch_job_bot.matching.geo import classify_location, passes_geo
from arch_job_bot.models import JobPosting


# ── ISO-8601 date (Maavarim content attr) ────────────────────────────────────
def test_iso_date_normalization():
    assert normalize_posted_date("2026-06-22T14:04:11+03:00") == "22/06/2026"
    assert normalize_posted_date("2026-05-03T00:00:00") == "03/05/2026"


# ── procurement-tender reject gate (salaried-only) ───────────────────────────
def test_procurement_tenders_rejected():
    assert not classify("מכרז מסגרת למתן שירותי אדריכלות לעירייה").accepted
    assert not classify("קול קורא לאדריכלים להקמת מאגר יועצים").accepted
    assert not classify("הזמנה להציע הצעות לתכנון אדריכלי").accepted


def test_salaried_manpower_tender_still_accepted():
    # municipal manpower tender (מכרז כוח אדם) is salaried → must pass
    assert classify("מכרז כוח אדם 24/2026 - בודק/ת תכניות במחלקת תכנון").accepted


# ── commuter-ring-only geo (far Negev excluded) ──────────────────────────────
def test_far_negev_excluded():
    assert classify_location("המשרה באשקלון").excluded_city is not None
    ok, _ = passes_geo("דרוש אדריכל באשקלון אזור הדרום", arch_only_source=False)
    assert ok is False                      # excluded city wins over the "דרום" signal
    ok, _ = passes_geo("דרוש אדריכל במועצה אזורית אשכול", arch_only_source=False)
    assert ok is False


def test_commuter_town_still_in_scope():
    ok, _ = passes_geo("דרוש אדריכל בדימונה", arch_only_source=False)
    assert ok is True


# ── challenge-page guard ─────────────────────────────────────────────────────
def test_challenge_detection():
    assert _is_challenge("<html><title>Just a moment...</title>")
    assert _is_challenge("Please wait while we are checking your browser before accessing")
    assert not _is_challenge("<html><body>משרה חדשה באדריכלות</body></html>")


# ── conservative cross-source dedup ──────────────────────────────────────────
def _job(source, title, city="באר שבע", job_id=None):
    return JobPosting(source=source, job_id=job_id or title, title=title, url="https://x",
                      city=city, raw_text=title)


def test_cross_source_suppresses_specific_repost(tmp_path):
    store = SeenStore(tmp_path / "d.sqlite3")
    long_title = "בודק/ת תכניות במחלקת תכנון במנהל ההנדסה בעיריית באר שבע"
    a = _job("beersheva_muni", long_title)
    assert store.is_new(a)
    store.record(a)
    # same specific job surfaced by another source → suppressed
    b = _job("maavarim", long_title)
    assert store.is_new(b) is False
    store.close()


def test_cross_source_keeps_generic_titles(tmp_path):
    store = SeenStore(tmp_path / "d.sqlite3")
    a = _job("alljobs", "אדריכל/ית", job_id="1")
    store.record(a)
    # short/generic title from another source → NOT suppressed (never-miss bias)
    b = _job("drushim", "אדריכל/ית", job_id="2")
    assert store.is_new(b) is True
    store.close()


def test_count_by_source(tmp_path):
    store = SeenStore(tmp_path / "d.sqlite3")
    assert store.count_by_source("maavarim") == 0
    store.record(_job("maavarim", "מהנדס/ת רישוי במועצה", job_id="n1"))
    assert store.count_by_source("maavarim") == 1
    store.close()


# ── weekly digest ────────────────────────────────────────────────────────────
def test_weekly_digest(tmp_path):
    store = SeenStore(tmp_path / "d.sqlite3")
    j1 = _job("beersheva_muni", "בודק/ת תכניות במחלקת תכנון", job_id="a")
    j1.sub_field = "רישוי והיתרים"
    j2 = _job("maavarim", "אדריכל/ית למועצה אזורית", job_id="b")
    j2.sub_field = "אדריכלות כללית"
    store.record(j1)
    store.record(j2)
    counts = store.digest_counts(7)
    assert counts["total"] == 2
    assert counts["by_subfield"]["רישוי והיתרים"] == 1
    text = format_weekly_digest(counts)
    assert "2" in text and "רישוי והיתרים" in text
    # empty-week digest
    assert "ממשיך לסרוק" in format_weekly_digest({"days": 7, "total": 0,
                                                  "by_subfield": {}, "by_source": {}})
    store.close()
