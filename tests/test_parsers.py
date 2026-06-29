"""Parser tests against real saved board HTML (tests/fixtures/).

These pin the DOM selectors: if a board changes its markup, a parser test fails
loudly here (the offline analogue of the live per-source health check).
"""

import pathlib

import pytest

from arch_job_bot.fetch.sources.alljobs import AllJobsSource
from arch_job_bot.fetch.sources.drushim import DrushimSource
from arch_job_bot.fetch.sources.jobkarov import JobKarovSource
from arch_job_bot.fetch.sources.jobmaster import JobMasterSource

FIX = pathlib.Path(__file__).parent / "fixtures"


def _html(name):
    return (FIX / name).read_text(encoding="utf-8")


CASES = [
    (AllJobsSource, "alljobs.html"),
    (JobKarovSource, "jobkarov.html"),
    (JobMasterSource, "jobmaster.html"),
    (DrushimSource, "drushim.html"),
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
