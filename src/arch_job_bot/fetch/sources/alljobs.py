"""AllJobs (alljobs.co.il) guest-search scraper.

Server-rendered HTML. Each job card is `div[id^="job-box-container{JobID}"]` with:
  title   div.job-content-top-title a  (h2);  href=/Search/UploadSingle.aspx?JobID=
  company div.job-content-top-title div.T14 a
  date    div.job-content-top-date     (relative, e.g. "לפני 35 דקות")
  salary  div.job-content-top-salary
  location div.job-content-top-location (may list several city anchors)
  desc    div.job-content-top-desc
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ...models import JobPosting
from ..base import BaseSource, clean, normalize_posted_date

BASE = "https://www.alljobs.co.il"


class AllJobsSource(BaseSource):
    name = "alljobs"

    def parse(self, html: str, url: str) -> list[JobPosting]:
        tree = HTMLParser(html)
        jobs: list[JobPosting] = []
        for box in tree.css('div[id^="job-box-container"]'):
            box_id = (box.attributes.get("id") or "")
            m = re.search(r"(\d+)", box_id)
            job_id = m.group(1) if m else None

            title_a = box.css_first("div.job-content-top-title a")
            if not title_a:
                continue
            title = clean(title_a.text())
            href = title_a.attributes.get("href") or f"/Search/UploadSingle.aspx?JobID={job_id}"
            full_url = urljoin(BASE, href)

            company_el = box.css_first("div.job-content-top-title div.T14 a")
            company = clean(company_el.text()) if company_el else None

            date_el = box.css_first("div.job-content-top-date")
            posted = normalize_posted_date(date_el.text()) if date_el else None

            salary_el = box.css_first("div.job-content-top-salary")
            salary = None
            if salary_el:
                salary = clean(salary_el.text()).replace("שכר:", "").replace("שכר", "").strip() or None

            loc_el = box.css_first("div.job-content-top-location")
            location = clean(loc_el.text()).replace("מיקום המשרה:", "").strip() if loc_el else None

            desc_el = box.css_first("div.job-content-top-desc")
            description = clean(desc_el.text()) if desc_el else ""

            raw = clean(box.text())[:4000]
            jobs.append(JobPosting(
                source=self.name, job_id=job_id, title=title, url=full_url,
                company=company, city=location, posted_date=posted, salary=salary,
                raw_text=raw, description=description,
            ))
        return jobs
