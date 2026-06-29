"""Drushim (drushim.co.il) scraper — server-rendered Vue/Vuetify markup.

Each job: `div.job-item` containing `div[listingid]` with:
  title    span.job-url   (inside h3)
  link     a[href^="/job/"]   →  /job/<id>/<hash>/
  company  p a span.bidi
  intro    p.display-18 / div.job-intro
  date     relative text in the card ("לפני 2 שעות") — extracted from full text.

NOTE: Drushim cards sometimes show "מספר מקומות" instead of a city, so geo is run on
the full card text; the configured query is the national keyword path. Finding the
correct area-path (Beer Sheva) or the internal JSON API is a v2 recall upgrade.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ...models import JobPosting
from ..base import BaseSource, clean, normalize_posted_date

BASE = "https://www.drushim.co.il"


class DrushimSource(BaseSource):
    name = "drushim"

    def parse(self, html: str, url: str) -> list[JobPosting]:
        tree = HTMLParser(html)
        jobs: list[JobPosting] = []
        for card in tree.css("div.job-item"):
            main = card.css_first("div[listingid]")
            job_id = main.attributes.get("listingid") if main else None

            title_el = card.css_first("span.job-url") or card.css_first("h3")
            title = clean(title_el.text()) if title_el else None
            if not title:
                continue

            link = card.css_first('a[href^="/job/"]')
            href = link.attributes.get("href") if link else None
            full_url = urljoin(BASE, href) if href else BASE
            if not job_id and href:
                m = re.search(r"/job/(\d+)", href)
                job_id = m.group(1) if m else None

            comp_el = card.css_first("span.bidi")
            company = clean(comp_el.text()) if comp_el else None

            raw = clean(card.text())[:4000]
            posted = normalize_posted_date(raw)
            jobs.append(JobPosting(
                source=self.name, job_id=job_id, title=title, url=full_url,
                company=company, city=None, posted_date=posted, raw_text=raw,
            ))
        return jobs
