"""Build the Hebrew alert message from a JobPosting.

Fields the user asked for: publish date, salary, company, sub-field, location, link.
Missing salary/company render as "לא צוין" (not stated) rather than being dropped,
so a blank is visibly "not captured" instead of looking like a parsing bug.
"""

from __future__ import annotations

from html import escape

from ..models import JobPosting

NOT_STATED = "לא צוין"

# Friendly Hebrew source names for the alert footer.
SOURCE_NAMES = {
    "alljobs": "AllJobs",
    "drushim": "דרושים",
    "jobmaster": "JobMaster",
    "jobkarov": "JobKarov",
    "archijob": "ארכיג'וב",
    "maavarim": "מעברים נגב",
    "beersheva_muni": "עיריית באר שבע",
    "isra_arch": "התאחדות האדריכלים",
    "govojobs": "GOVO Jobs",
}


def _val(v: str | None) -> str:
    v = (v or "").strip()
    return v if v else NOT_STATED


def source_label(source: str) -> str:
    return SOURCE_NAMES.get(source, source)


def format_telegram_html(job: JobPosting) -> str:
    """Telegram message (parse_mode=HTML). Keep links bare so the preview card shows."""
    title = escape(_val(job.title))
    company = escape(_val(job.company))
    sub_field = escape(_val(job.sub_field))
    location = escape(_val(job.city or job.region))
    salary = escape(_val(job.salary))
    posted = escape(_val(job.posted_date))
    url = escape(job.url or "", quote=True)
    src = escape(source_label(job.source))

    lines = [
        "🏛️ <b>משרה חדשה באדריכלות — באר שבע והסביבה</b>",
        "",
        f"📌 <b>{title}</b>",
        f"🏢 חברה: {company}",
        f"🗂️ תחום: {sub_field}",
        f"📍 מיקום: {location}",
        f"💰 שכר: {salary}",
        f"🗓️ פורסם: {posted}",
        f"🔗 {url}" if url else None,   # None → skipped; "" separator → kept
        f"🛰️ מקור: {src}",
    ]
    return "\n".join(line for line in lines if line is not None)


def format_plaintext(job: JobPosting) -> str:
    """Plain text variant (email / logs / SMS / WhatsApp templates)."""
    return (
        "🏛️ משרה חדשה באדריכלות — באר שבע והסביבה\n\n"
        f"📌 {_val(job.title)}\n"
        f"🏢 חברה: {_val(job.company)}\n"
        f"🗂️ תחום: {_val(job.sub_field)}\n"
        f"📍 מיקום: {_val(job.city or job.region)}\n"
        f"💰 שכר: {_val(job.salary)}\n"
        f"🗓️ פורסם: {_val(job.posted_date)}\n"
        f"🔗 {job.url or ''}\n"
        f"🛰️ מקור: {source_label(job.source)}\n"
    )
