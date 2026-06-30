"""Parser tests against real saved board HTML (tests/fixtures/).

These pin the DOM selectors: if a board changes its markup, a parser test fails
loudly here (the offline analogue of the live per-source health check).
"""

import pathlib

import pytest

from arch_job_bot.fetch.sources.alljobs import AllJobsSource
from arch_job_bot.fetch.sources.beersheva_muni import BeerShevaMuniSource
from arch_job_bot.fetch.sources.drushim import DrushimSource
from arch_job_bot.fetch.sources.jobkarov import JobKarovSource
from arch_job_bot.fetch.sources.jobmaster import JobMasterSource
from arch_job_bot.fetch.sources.maavarim import MaavarimSource

FIX = pathlib.Path(__file__).parent / "fixtures"


def _html(name):
    return (FIX / name).read_text(encoding="utf-8")


CASES = [
    (AllJobsSource, "alljobs.html"),
    (JobKarovSource, "jobkarov.html"),
    (JobMasterSource, "jobmaster.html"),
    (DrushimSource, "drushim.html"),
    (BeerShevaMuniSource, "beersheva_muni.html"),
    (MaavarimSource, "maavarim.html"),
]


@pytest.mark.parametrize("cls,fixture", CASES)
def test_parser_extracts_jobs(cls, fixture):
    src = cls(http=None)
    jobs = src.parse(_html(fixture), "https://example/")
    assert len(jobs) >= 3, f"{cls.name}: expected several jobs, got {len(jobs)}"
    for j in jobs:
        assert j.source == cls.name
        assert j.title and j.title.strip()
        assert j.url and j.url.startswith("http")
        assert j.job_id, f"{cls.name}: missing job_id for {j.title!r}"
        assert j.raw_text


@pytest.mark.parametrize("cls,fixture", CASES)
def test_parser_job_ids_unique_and_stable(cls, fixture):
    src = cls(http=None)
    jobs = src.parse(_html(fixture), "https://example/")
    ids = [j.job_id for j in jobs]
    # IDs should be mostly unique (a board may legitimately repeat a promoted job).
    assert len(set(ids)) >= max(3, len(ids) // 2)


# The general boards that produced the bad alerts must isolate a clean JD snippet,
# so relevance is judged on the role and not on the noisy whole-card blob.
@pytest.mark.parametrize("cls,fixture", [
    (AllJobsSource, "alljobs.html"),
    (JobMasterSource, "jobmaster.html"),
    (DrushimSource, "drushim.html"),
])
def test_description_extracted(cls, fixture):
    jobs = cls(http=None).parse(_html(fixture), "https://example/")
    assert any(j.description.strip() for j in jobs), \
        f"{cls.name}: no clean description snippet extracted from any card"


def test_match_text_excludes_company_and_chrome():
    """A non-architecture role at an architecture firm must NOT be rescued: match_text
    (title + clean description) excludes the company name and the card blob."""
    from arch_job_bot.matching.classifier import classify
    from arch_job_bot.models import JobPosting

    p = JobPosting(
        source="alljobs", title="דרוש/ה איש מכירות לסניף", url="https://x",
        company="משרד אדריכלות מוביל", city="באר שבע",
        description="אנו מגייסים איש/אשת מכירות נמרץ/ה לסניף החדש",
        raw_text="כל טקסט הכרטיס כולל אדריכלות כללית ומשרות דומות",
    )
    assert "אדריכלות" in p.full_text()          # chrome word is present in the blob...
    assert "אדריכלות" not in p.match_text()      # ...but not in the role text
    assert not classify(p.match_text(), title=p.title).accepted
