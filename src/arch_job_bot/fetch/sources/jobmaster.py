"""JobMaster (jobmaster.co.il) scraper.

Each job: `article[id^="misra{JobID}"]` with:
  title   a.CardHeader          href=/jobs/checknum.asp?key=
  date    span.Gray             (relative, "פורסם לפני 2 שעות")
  company a.CompanyNameLink
  location li.jobLocation
  desc    div.jobShortDescription
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ...models import JobPosting
from ..base import BaseSource, clean, normalize_posted_date

BASE = "https://www.jobmaster.co.il"


class JobMasterSource(BaseSource):
    name = "jobmaster"

    def parse(self, html: str, url: str) -> list[JobPosting]:
        tree = HTMLParser(html)
        jobs: list[JobPosting] = []
        for art in tree.css('article[id^="misra"]'):
            art_id = art.attributes.get("id") or ""
            m = re.search(r"(\d+)", art_id)
            job_id = m.group(1) if m else None

            title_a = art.css_first("a.CardHeader")
            if not title_a:
                continue
            title = clean(title_a.text())
            href = title_a.attributes.get("href") or (f"/jobs/checknum.asp?key={job_id}" if job_id else "")
            full_url = urljoin(BASE, href) if href else BASE

            comp_el = art.css_first("a.CompanyNameLink")
            company = clean(comp_el.text()) if comp_el else None

            loc_el = art.css_first("li.jobLocation")
            location = clean(loc_el.text()) if loc_el else None

            date_el = art.css_first("span.Gray")
            posted = normalize_posted_date(date_el.text()) if date_el else None

            raw = clean(art.text())[:4000]
            jobs.append(JobPosting(
                source=self.name, job_id=job_id, title=title, url=full_url,
                company=company, city=location, posted_date=posted, raw_text=raw,
            ))
        return jobs
