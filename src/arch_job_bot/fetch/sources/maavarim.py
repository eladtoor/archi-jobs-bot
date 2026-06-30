"""Maavarim Negev employment centers — mnz.org.il (N. Negev) + mem.org.il (W. Negev).

Two near-identical Drupal sites; one parser, base host derived from the query URL. Each
posting is a teaser `div[about="/he/node/<ID>"]` with an `h3` title and a
`span.date-display-single` carrying both an ISO `content` attr and dd/mm/yyyy text.
Aggregates South regional-council + municipal SALARIED engineering/planning/permit roles
(ועדה מקומית / בודק היתרים / מהנדס-אדריכל). Strict commuter geo (titles/bodies name the town;
far Western/Northern-Negev towns are in geo.yaml exclude_cities).
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from selectolax.parser import HTMLParser

from ...models import JobPosting
from ..base import BaseSource, clean, normalize_posted_date

_REF_LEAD = re.compile(r"^\s*\d{4,}\s*[-–]\s*")          # leading "20911- "
_REF_TRAIL = re.compile(r"\s*[A-Za-z]{0,3}\d{4,}\s*$")    # trailing "RO80112" / "980578"


class MaavarimSource(BaseSource):
    name = "maavarim"
    sanity_marker = "field_job_area_tid"     # the exposed area filter — always present

    def parse(self, html: str, url: str) -> list[JobPosting]:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        tree = HTMLParser(html)
        jobs: list[JobPosting] = []
        for node in tree.css('div[about^="/he/node/"]'):
            about = node.attributes.get("about") or ""
            m = re.search(r"/node/(\d+)", about)
            job_id = m.group(1) if m else None

            h3 = node.css_first("h3")
            title = clean(h3.text()) if h3 else None
            if not title:
                continue
            title = _REF_TRAIL.sub("", _REF_LEAD.sub("", title)).strip() or title

            date_el = node.css_first("span.date-display-single")
            posted = None
            if date_el:
                posted = normalize_posted_date(date_el.attributes.get("content") or date_el.text())

            raw = clean(node.text())[:4000]
            jobs.append(JobPosting(
                source=self.name, job_id=job_id, title=title,
                url=urljoin(base, about), company=None, city=None,
                posted_date=posted, raw_text=raw,
            ))
        return jobs
