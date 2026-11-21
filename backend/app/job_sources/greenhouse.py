"""Greenhouse job board API, one public board per company. https://developers.greenhouse.io/job-board.html"""
from datetime import datetime
from typing import Iterator

from app.job_sources.base import FetchReport, JobPosting
from app.job_sources.http import JsonClient, SourceUnavailable
from app.job_sources.text import html_to_text

API_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


def _parse_time(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


class GreenhouseAdapter:
    name = "greenhouse"
    attribution = "Greenhouse job board"
    attribution_url = "https://www.greenhouse.com/"
    europe_only = False

    def __init__(self, boards: list[str]) -> None:
        self.boards = boards

    def fetch(self, client: JsonClient, report: FetchReport) -> Iterator[JobPosting]:
        for board in self.boards:
            try:
                body = client.get_json(API_URL.format(board=board), {"content": "true"})
            except SourceUnavailable as error:
                report.errors.append(f"{board}: {error}")
                continue
            report.requests += 1
            for row in body.get("jobs") or []:
                posting = self._posting(board, row)
                if posting:
                    report.fetched += 1
                    yield posting

    def verify(self, client: JsonClient) -> dict[str, int | str]:
        """Job count per board token, or the error; used to keep only working tokens."""
        result: dict[str, int | str] = {}
        for board in self.boards:
            try:
                result[board] = len(client.get_json(API_URL.format(board=board)).get("jobs") or [])
            except SourceUnavailable as error:
                result[board] = str(error)
        return result

    def _posting(self, board: str, row: dict) -> JobPosting | None:
        if row.get("id") is None or not row.get("title"):
            return None
        offices = [office.get("location") or office.get("name") or "" for office in row.get("offices") or []]
        names = [((row.get("location") or {}).get("name") or "").strip(), *(office.strip() for office in offices)]
        location = "; ".join(name for name in dict.fromkeys(names) if name)
        time_type = next((str(item.get("value")) for item in row.get("metadata") or []
                          if str(item.get("name", "")).lower() in {"time type", "employment type"}
                          and item.get("value")), "")
        return JobPosting(
            source=self.name,
            # Job IDs are unique per board, so the board token is part of the identity.
            external_id=f"{board}:{row['id']}",
            title=str(row["title"]).strip(),
            company=str(row.get("company_name") or board).strip(),
            location=location[:255],
            employment_type=time_type[:80],
            description=html_to_text(row.get("content") or ""),
            external_url=str(row.get("absolute_url") or ""),
            posted_at=_parse_time(row.get("first_published")) or _parse_time(row.get("updated_at")),
            remote="remote" in location.lower(),
            declared_language=row.get("language"),
        )
