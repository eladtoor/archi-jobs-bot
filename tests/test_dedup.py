"""Dedup store invariants: alert exactly once, alert-then-commit, no re-alert on repost."""

from arch_job_bot.dedup import SeenStore
from arch_job_bot.models import JobPosting


def _job(job_id="100", source="alljobs", title="אדריכל/ית", url="https://x/100"):
    return JobPosting(source=source, job_id=job_id, title=title, url=url, raw_text=title)


def test_is_new_then_recorded(tmp_path):
    store = SeenStore(tmp_path / "d.sqlite3")
    j = _job()
    assert store.is_new(j) is True
    assert store.record(j) is True          # newly inserted
    assert store.is_new(j) is False         # now seen
    assert store.record(j) is False         # idempotent, no second row
    store.close()


def test_alert_then_commit_simulation(tmp_path):
    """If delivery 'fails' we must NOT record — so it retries next cycle."""
    store = SeenStore(tmp_path / "d.sqlite3")
    j = _job()
    assert store.is_new(j)
    delivered = False                        # simulate a failed send
    if delivered:
        store.record(j)
    assert store.is_new(j) is True           # still new → will retry
    store.close()


def test_repost_same_id_not_realerted(tmp_path):
    store = SeenStore(tmp_path / "d.sqlite3")
    store.record(_job(job_id="55"))
    # same id, different surrounding text (repost) → still seen, not new
    reposted = _job(job_id="55", title="אדריכל/ית — פורסם מחדש")
    assert store.is_new(reposted) is False
    store.close()


def test_no_native_id_uses_content_hash(tmp_path):
    store = SeenStore(tmp_path / "d.sqlite3")
    a = JobPosting(source="fb", job_id=None, title="אדריכל בבאר שבע", url="u", raw_text="אדריכל בבאר שבע")
    assert store.is_new(a)
    store.record(a)
    # identical text, no id → same content hash → seen
    b = JobPosting(source="fb", job_id=None, title="אדריכל בבאר שבע", url="u2", raw_text="אדריכל בבאר שבע")
    assert store.is_new(b) is False
    store.close()


def test_seed_marks_without_counting_as_new(tmp_path):
    store = SeenStore(tmp_path / "d.sqlite3")
    jobs = [_job(job_id=str(i)) for i in range(5)]
    assert store.seed(jobs) == 5
    assert store.count() == 5
    for j in jobs:
        assert store.is_new(j) is False
    store.close()
