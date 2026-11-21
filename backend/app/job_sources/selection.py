"""Which fetched postings become live jobs: English, located in Europe or remote, newest first (D053)."""
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.job_sources.base import JobPosting
from app.job_sources.text import detect_language, is_europe_or_remote

_OLDEST = datetime.min.replace(tzinfo=timezone.utc)


@dataclass
class SelectionReport:
    considered: int = 0
    selected: int = 0
    skipped_language: Counter = field(default_factory=Counter)
    skipped_location: int = 0
    skipped_empty: int = 0
    skipped_duplicate_id: int = 0
    over_cap: int = 0


def select_postings(postings: list[JobPosting], max_active: int, english_only: bool = True,
                    europe_or_remote_only: bool = True, europe_only_sources: frozenset[str] = frozenset()
                    ) -> tuple[list[JobPosting], SelectionReport]:
    """Filter, then keep the `max_active` newest postings (no date sorts last)."""
    report = SelectionReport(considered=len(postings))
    seen: set[tuple[str, str]] = set()
    kept: list[JobPosting] = []
    for posting in postings:
        key = (posting.source, posting.external_id)
        if key in seen:
            report.skipped_duplicate_id += 1
            continue
        seen.add(key)
        if not posting.title.strip() or len(posting.description.strip()) < 40:
            report.skipped_empty += 1
            continue
        if english_only:
            language = detect_language(f"{posting.title}\n{posting.description}")
            if language != "en":
                report.skipped_language[language] += 1
                continue
        if (europe_or_remote_only and posting.source not in europe_only_sources
                and not is_europe_or_remote(posting.location, posting.remote)):
            report.skipped_location += 1
            continue
        kept.append(posting)
    kept.sort(key=lambda p: (p.posted_at or _OLDEST, p.source, p.external_id), reverse=True)
    report.over_cap = max(0, len(kept) - max_active)
    selected = kept[:max_active]
    report.selected = len(selected)
    return selected, report
