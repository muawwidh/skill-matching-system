"""One interface for live job sources (D053)."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator, Protocol

from app.job_sources.http import JsonClient


@dataclass
class JobPosting:
    """A posting as read from a source, description already converted to plain text."""
    source: str
    external_id: str
    title: str
    company: str
    location: str
    employment_type: str
    description: str
    external_url: str
    posted_at: datetime | None
    remote: bool = False
    declared_language: str | None = None


@dataclass
class FetchReport:
    source: str
    fetched: int = 0
    requests: int = 0
    errors: list[str] = field(default_factory=list)


class JobSourceAdapter(Protocol):
    name: str
    #: Attribution shown next to jobs from this source.
    attribution: str
    attribution_url: str

    def fetch(self, client: JsonClient, report: FetchReport) -> Iterator[JobPosting]: ...
