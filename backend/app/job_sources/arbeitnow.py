"""Arbeitnow public job board API (no key). https://www.arbeitnow.com/api/job-board-api"""
from datetime import datetime, timezone
from typing import Iterator

from app.job_sources.base import FetchReport, JobPosting
from app.job_sources.http import JsonClient, SourceUnavailable
from app.job_sources.text import html_to_text

API_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowAdapter:
    name = "arbeitnow"
    attribution = "Arbeitnow"
    # The API terms ask for a link back to the site.
    attribution_url = "https://www.arbeitnow.com/"
    # A Europe-focused board (mostly Germany); its town names are not matched by the location filter.
    europe_only = True

    def __init__(self, max_pages: int = 10) -> None:
        self.max_pages = max_pages

    def fetch(self, client: JsonClient, report: FetchReport) -> Iterator[JobPosting]:
        for page in range(1, self.max_pages + 1):
            try:
                body = client.get_json(API_URL, {"page": page})
            except SourceUnavailable as error:
                report.errors.append(f"page {page}: {error}")
                return
            report.requests += 1
            rows = body.get("data") or []
            for row in rows:
                posting = self._posting(row)
                if posting:
                    report.fetched += 1
                    yield posting
            if not rows or not (body.get("links") or {}).get("next"):
                return

    def _posting(self, row: dict) -> JobPosting | None:
        if not row.get("slug") or not row.get("title"):
            return None
        created = row.get("created_at")
        return JobPosting(
            source=self.name,
            external_id=str(row["slug"]),
            title=str(row["title"]).strip(),
            company=str(row.get("company_name") or "").strip(),
            location=str(row.get("location") or "").strip(),
            employment_type=", ".join(row.get("job_types") or [])[:80],
            description=html_to_text(row.get("description") or ""),
            external_url=str(row.get("url") or ""),
            posted_at=datetime.fromtimestamp(created, tz=timezone.utc) if isinstance(created, (int, float)) else None,
            remote=bool(row.get("remote")),
        )
