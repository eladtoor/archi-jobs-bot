"""JobKarov (jobkarov.com) scraper — engineers/architects board, cleanest markup.

Each job: `div.lisite` with data-id, data-href. Inside:
  title   span.h4 a
  date    div.date  (e.g. "עודכן היום")
  company span.company a.link
  location span.address
  desc    span.description
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ...models import JobPosting
from ..base import BaseSource, clean, normalize_posted_date

BASE = "https://www.jobkarov.com"


class JobKarovSource(BaseSource):
    name = "jobkarov"

    def parse(self, html: str, url: str) -> list[JobPosting]:
        tree = HTMLParser(html)
        jobs: list[JobPosting] = []
        for card in tree.css("div.lisite"):
            attrs = card.attributes
            job_id = attrs.get("data-id")
            href = attrs.get("data-href") or ""
            full_url = urljoin(BASE, href) if href else BASE

            title_el = card.css_first("span.h4 a") or card.css_first("span.h4")
            title = clean(title_el.text()) if title_el else None
            if not title:
                continue

            date_el = card.css_first("div.date")
            posted = normalize_posted_date(date_el.text()) if date_el else None

            comp_el = card.css_first("span.company a") or card.css_first("span.company")
            company = None
            if comp_el:
                company = clean(comp_el.text()).replace("שם החברה:", "").strip() or None

            addr_el = card.css_first("span.address")
            location = None
            if addr_el:
                location = clean(addr_el.text()).replace("מיקום המשרה:", "").replace("ועוד", "").strip() or None

            raw = clean(card.text())[:4000]
            if not job_id:
                m = re.search(r"/Site/(\d+)", href)
                job_id = m.group(1) if m else None
            jobs.append(JobPosting(
                source=self.name, job_id=job_id, title=title, url=full_url,
                company=company, city=location, posted_date=posted, raw_text=raw,
            ))
        return jobs
