"""Which fetched postings become live jobs: English, located in Europe or remote, newest first (D053),
with no source above its share of the cap (D058)."""
import math
from typing import Callable, Iterable, TypeVar
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
    over_source_share: int = 0


T = TypeVar("T")


def source_limit(max_active: int, max_source_share: float) -> int:
    """Most live jobs one source may hold: floor(share x cap), at least 1."""
    return max_active if max_source_share >= 1 else max(1, math.floor(max_active * max_source_share))


def allocate(items: Iterable[T], max_active: int, max_source_share: float, source: Callable[[T], str],
             newest_first_key: Callable[[T], tuple]) -> tuple[list[T], list[T], list[T]]:
    """Newest first; skip an item once its source holds its share or the cap is reached.

    Returns (kept, over_source_share, over_cap). Other sources fill places a full
    source cannot take, so the cap is still used when one source dominates.
    """
    limit = source_limit(max_active, max_source_share)
    kept: list[T] = []
    over_share: list[T] = []
    over_cap: list[T] = []
    per_source: dict[str, int] = {}
    for item in sorted(items, key=newest_first_key, reverse=True):
        name = source(item)
        if len(kept) >= max_active:
            over_cap.append(item)
        elif per_source.get(name, 0) >= limit:
            over_share.append(item)
        else:
            kept.append(item)
            per_source[name] = per_source.get(name, 0) + 1
    return kept, over_share, over_cap


def select_postings(postings: list[JobPosting], max_active: int, english_only: bool = True,
                    europe_or_remote_only: bool = True, europe_only_sources: frozenset[str] = frozenset(),
                    max_source_share: float = 1.0) -> tuple[list[JobPosting], SelectionReport]:
    """Filter, then keep the `max_active` newest postings, at most `max_source_share` of
    the cap per source (no date sorts last)."""
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
    selected, over_share, over_cap = allocate(
        kept, max_active, max_source_share, lambda p: p.source,
        lambda p: (p.posted_at or _OLDEST, p.source, p.external_id))
    report.over_cap = len(over_cap)
    report.over_source_share = len(over_share)
    report.selected = len(selected)
    return selected, report
