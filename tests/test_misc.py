"""Sub-field derivation, date normalization, and message formatting."""

from datetime import date

from arch_job_bot.alert import formatter
from arch_job_bot.fetch.base import normalize_posted_date
from arch_job_bot.matching.subfield import derive_subfield
from arch_job_bot.models import JobPosting


def test_subfield():
    assert derive_subfield("עורך/ת בקשה להיתר ברשות רישוי") == "רישוי והיתרים"
    assert derive_subfield("מתכנן/ת ערים לוועדה מקומית") == "תכנון ערים"
    assert derive_subfield("אדריכל/ית נוף") == "אדריכלות נוף"
    assert derive_subfield("מעצב/ת פנים") == "עיצוב פנים"
    assert derive_subfield("שרטט/ת Revit") == "שרטוט והנדסאי"
    assert derive_subfield("דרוש/ה אדריכל/ית") == "אדריכלות כללית"


def test_normalize_posted_date_relative():
    today = date(2026, 6, 29)
    assert normalize_posted_date("פורסם לפני 15 דקות", today) == "29/06/2026"
    assert normalize_posted_date("לפני 3 ימים", today) == "26/06/2026"
    assert normalize_posted_date("עודכן היום", today) == "29/06/2026"
    assert normalize_posted_date("אתמול", today) == "28/06/2026"


def test_normalize_posted_date_absolute():
    assert normalize_posted_date("29/06/2026") == "29/06/2026"
    assert normalize_posted_date("1/6/26") == "01/06/2026"


def test_formatter_fills_missing_fields():
    j = JobPosting(source="alljobs", job_id="1", title="אדריכל/ית רישוי",
                   url="https://x/1", company=None, city="באר שבע",
                   sub_field="רישוי והיתרים", salary=None, posted_date="29/06/2026")
    html = formatter.format_telegram_html(j)
    assert "לא צוין" in html              # missing company + salary → placeholder
    assert "באר שבע" in html
    assert "https://x/1" in html
    assert "<b>" in html                  # HTML formatting present


def test_formatter_escapes_html():
    j = JobPosting(source="alljobs", job_id="1", title="אדריכל <script> & co",
                   url="https://x/1", raw_text="x")
    html = formatter.format_telegram_html(j)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
