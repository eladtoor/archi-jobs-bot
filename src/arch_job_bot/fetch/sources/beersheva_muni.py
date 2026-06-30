"""Beer Sheva municipality careers (מכרזי כוח אדם) — SharePoint, plain HTML.

Single page `Careers.aspx`. Each vacancy = `tr.rowMain` with cells
[icon, title, tender_no NN/YYYY, closing dd/mm/yyyy HH:MM]; the following `tr.rowData`
panel holds a `List6/DispForm.aspx?ID=<stableID>` link. All jobs are in Beer Sheva
(geo_trusted) — the classifier drops non-architecture tenders (drivers, social workers…).
Salaried by construction (מכרזי כוח אדם).
"""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser

from ...models import JobPosting
from ..base import BaseSource, clean

DISPFORM = "https://www.beer-sheva.muni.il/City/FreeInfo/Lists/List6/DispForm.aspx?ID="


class BeerShevaMuniSource(BaseSource):
    name = "beersheva_muni"
    geo_trusted = True               # every tender is Beer Sheva
    sanity_marker = "מספר מכרז"       # column header — present even with 0 open tenders

    def parse(self, html: str, url: str) -> list[JobPosting]:
        tree = HTMLParser(html)
        jobs: list[JobPosting] = []
        for row in tree.css("tr.rowMain"):
            tds = row.css("td")
            if len(tds) < 4:
                continue
            title = clean(tds[1].text())
            tender_no = clean(tds[2].text())
            closing = clean(tds[3].text())
            if not title:
                continue

            # Stable List6 ID from the adjacent detail panel (regex tolerates the ID
            # appearing inside social-share URLs — same numeric ID either way).
            detail_id = None
            sib = row.next
            while sib is not None and sib.tag != "tr":
                sib = sib.next
            if sib is not None:
                m = re.search(r"DispForm\.aspx\?ID=(\d+)", sib.html or "")
                if m:
                    detail_id = m.group(1)

            job_id = detail_id or tender_no or title
            job_url = (DISPFORM + detail_id) if detail_id else url
            raw = f"{title} מכרז {tender_no} עיריית באר שבע להגשה עד {closing}"
            jobs.append(JobPosting(
                source=self.name, job_id=job_id, title=title, url=job_url,
                company="עיריית באר שבע", city="באר שבע", posted_date=None,
                raw_text=raw,
            ))
        return jobs
